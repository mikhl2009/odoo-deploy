from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission, get_db
from app.models.core import CoreUser
from app.models.mdm import MdmPartner, MdmSupplierProfile
from app.schemas.supply import SupplierCreate, SupplierResponse

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("purchase.read")),
) -> list[MdmPartner]:
    return db.scalars(select(MdmPartner).where(MdmPartner.partner_type == "supplier").order_by(MdmPartner.id.desc())).all()


@router.post("", response_model=SupplierResponse)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("purchase.write")),
) -> MdmPartner:
    supplier = MdmPartner(
        partner_type="supplier",
        legal_name=payload.legal_name,
        org_no=payload.org_no,
        vat_no=payload.vat_no,
        email=payload.email,
        phone=payload.phone,
        country_code=payload.country_code,
        active=True,
    )
    db.add(supplier)
    db.flush()
    db.add(
        MdmSupplierProfile(
            partner_id=supplier.id,
            lead_time_days=payload.lead_time_days,
            payment_terms=payload.payment_terms,
            incoterm=payload.incoterm,
            default_currency=payload.default_currency,
            min_order_value=payload.min_order_value,
        )
    )
    db.commit()
    db.refresh(supplier)
    return supplier
