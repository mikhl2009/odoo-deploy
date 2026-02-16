from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_permission
from app.models.core import CoreUser
from app.models.pim import (
    PimMediaAsset,
    PimPriceListItem,
    PimProduct,
    PimProductI18n,
    PimProductVariant,
    PimRevision,
)
from app.schemas.pim import (
    PriceBulkUpsertRequest,
    ProductCreate,
    ProductMediaCreate,
    ProductResponse,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
    RevisionResponse,
)
from app.services.audit import enqueue_outbox_event, log_audit_event

router = APIRouter(tags=["pim"])


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    sku: str | None = None,
    ean: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.read")),
) -> list[PimProduct]:
    stmt = select(PimProduct)
    if sku:
        stmt = stmt.where(PimProduct.sku.ilike(f"%{sku}%"))
    if ean:
        stmt = stmt.where(PimProduct.ean == ean)
    if status:
        stmt = stmt.where(PimProduct.status == status)
    return db.scalars(stmt.order_by(PimProduct.id.desc()).limit(500)).all()


@router.post("/products", response_model=ProductResponse)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("pim.write")),
) -> PimProduct:
    existing = db.scalar(
        select(PimProduct).where(PimProduct.company_id == payload.company_id, PimProduct.sku == payload.sku)
    )
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists in company")

    product = PimProduct(
        company_id=payload.company_id,
        sku=payload.sku,
        ean=payload.ean,
        gtin14=payload.gtin14,
        brand_id=payload.brand_id,
        status=payload.status,
        product_type=payload.product_type,
        is_tobacco=payload.is_tobacco,
    )
    db.add(product)
    db.flush()
    for translation in payload.translations:
        db.add(PimProductI18n(product_id=product.id, **translation.model_dump()))

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="pim_product",
        entity_id=str(product.id),
        action="create",
        before=None,
        after={"sku": product.sku, "status": product.status},
    )
    enqueue_outbox_event(
        db,
        event_name="product.updated",
        aggregate_type="product",
        aggregate_id=str(product.id),
        payload={"product_id": product.id, "sku": product.sku, "action": "create"},
    )
    db.commit()
    db.refresh(product)
    return product


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.read")),
) -> PimProduct:
    product = db.get(PimProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/products/{product_id}", response_model=ProductResponse)
def patch_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("pim.write")),
) -> PimProduct:
    product = db.get(PimProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = {
        "sku": product.sku,
        "ean": product.ean,
        "status": product.status,
        "product_type": product.product_type,
        "is_tobacco": product.is_tobacco,
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)

    latest_revision = db.scalar(
        select(func.coalesce(func.max(PimRevision.revision_no), 0)).where(
            PimRevision.entity_type == "pim_product",
            PimRevision.entity_id == str(product_id),
        )
    )
    db.add(
        PimRevision(
            entity_type="pim_product",
            entity_id=str(product_id),
            revision_no=int(latest_revision or 0) + 1,
            snapshot_jsonb={
                "sku": product.sku,
                "ean": product.ean,
                "status": product.status,
                "product_type": product.product_type,
                "is_tobacco": product.is_tobacco,
            },
            changed_by=user.id,
            changed_at=datetime.now(UTC).isoformat(),
        )
    )

    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="pim_product",
        entity_id=str(product.id),
        action="update",
        before=before,
        after={
            "sku": product.sku,
            "ean": product.ean,
            "status": product.status,
            "product_type": product.product_type,
            "is_tobacco": product.is_tobacco,
        },
    )
    enqueue_outbox_event(
        db,
        event_name="product.updated",
        aggregate_type="product",
        aggregate_id=str(product.id),
        payload={"product_id": product.id, "sku": product.sku, "action": "update"},
    )
    db.commit()
    db.refresh(product)
    return product


@router.post("/products/{product_id}/variants", response_model=ProductVariantResponse)
def create_product_variant(
    product_id: int,
    payload: ProductVariantCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("pim.write")),
) -> PimProductVariant:
    product = db.get(PimProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = PimProductVariant(product_id=product.id, **payload.model_dump())
    db.add(variant)
    db.flush()
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="pim_product_variant",
        entity_id=str(variant.id),
        action="create",
        before=None,
        after={"product_id": product_id, "sku": variant.sku},
    )
    enqueue_outbox_event(
        db,
        event_name="product.updated",
        aggregate_type="variant",
        aggregate_id=str(variant.id),
        payload={"product_id": product.id, "variant_id": variant.id, "sku": variant.sku},
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.patch("/variants/{variant_id}", response_model=ProductVariantResponse)
def patch_variant(
    variant_id: int,
    payload: ProductVariantUpdate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("pim.write")),
) -> PimProductVariant:
    variant = db.get(PimProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    before = {
        "barcode": variant.barcode,
        "tax_class": variant.tax_class,
        "active": variant.active,
        "nicotine_mg": str(variant.nicotine_mg) if variant.nicotine_mg else None,
        "tpd_code": variant.tpd_code,
    }
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, key, value)
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="pim_product_variant",
        entity_id=str(variant.id),
        action="update",
        before=before,
        after={
            "barcode": variant.barcode,
            "tax_class": variant.tax_class,
            "active": variant.active,
            "nicotine_mg": str(variant.nicotine_mg) if variant.nicotine_mg else None,
            "tpd_code": variant.tpd_code,
        },
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/products/{product_id}/media")
def create_product_media(
    product_id: int,
    payload: ProductMediaCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.write")),
) -> dict:
    product = db.get(PimProduct, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    values = payload.model_dump()
    values["product_id"] = product_id
    asset = PimMediaAsset(**values)
    db.add(asset)
    db.commit()
    return {"id": asset.id, "file_url": asset.file_url}


@router.post("/prices/bulk-upsert")
def bulk_upsert_prices(
    payload: PriceBulkUpsertRequest,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.write")),
) -> dict:
    upserted = 0
    for item in payload.items:
        existing = db.scalar(
            select(PimPriceListItem).where(
                PimPriceListItem.price_list_id == item.price_list_id,
                PimPriceListItem.variant_id == item.variant_id,
                PimPriceListItem.min_qty == item.min_qty,
            )
        )
        if existing:
            existing.unit_price = item.unit_price
            existing.customer_tier_code = item.customer_tier_code
        else:
            db.add(PimPriceListItem(**item.model_dump()))
        upserted += 1
    db.commit()
    return {"upserted": upserted}


@router.get("/catalog/search")
def search_catalog(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.read")),
) -> list[dict]:
    stmt = (
        select(PimProduct.id, PimProduct.sku, PimProduct.ean)
        .where(or_(PimProduct.sku.ilike(f"%{q}%"), PimProduct.ean.ilike(f"%{q}%")))
        .order_by(PimProduct.id.desc())
        .limit(25)
    )
    return [{"id": row.id, "sku": row.sku, "ean": row.ean} for row in db.execute(stmt)]


@router.get("/revisions/{entity_type}/{entity_id}", response_model=list[RevisionResponse])
def get_revisions(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("pim.read")),
) -> list[PimRevision]:
    stmt = (
        select(PimRevision)
        .where(PimRevision.entity_type == entity_type, PimRevision.entity_id == entity_id)
        .order_by(PimRevision.revision_no.desc())
    )
    return db.scalars(stmt).all()
