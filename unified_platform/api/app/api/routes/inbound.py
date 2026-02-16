from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.core import CoreUser
from app.models.inventory import (
    InvDiscrepancyReport,
    InvInboundShipment,
    InvInboundShipmentLine,
    InvReceivingScanEvent,
)
from app.schemas.supply import (
    InboundShipmentLineCreate,
    InboundShipmentCreate,
    InboundShipmentResponse,
    ShipmentDiscrepancyCreate,
    ShipmentScanRequest,
)
from app.services.audit import enqueue_outbox_event, log_audit_event
from app.ws.manager import ws_manager

router = APIRouter(prefix="/inbound-shipments", tags=["inbound-shipments"])


@router.get("", response_model=list[InboundShipmentResponse])
def list_shipments(
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("purchase.read")),
) -> list[InvInboundShipment]:
    return db.scalars(select(InvInboundShipment).order_by(InvInboundShipment.id.desc()).limit(500)).all()


@router.post("", response_model=InboundShipmentResponse)
def create_shipment(
    payload: InboundShipmentCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> InvInboundShipment:
    shipment = InvInboundShipment(**payload.model_dump(), status="draft")
    db.add(shipment)
    db.flush()
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="inv_inbound_shipment",
        entity_id=str(shipment.id),
        action="create",
        before=None,
        after={"status": shipment.status, "asn_number": shipment.asn_number},
    )
    db.commit()
    db.refresh(shipment)
    return shipment


@router.post("/{shipment_id}/start-receiving")
async def start_receiving(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    shipment = db.get(InvInboundShipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    shipment.status = "in_progress"
    shipment.receiver_user_id = user.id
    db.commit()
    await ws_manager.broadcast(f"receiving:{shipment_id}", {"event": "receiving_started", "shipment_id": shipment_id})
    return {"status": shipment.status}


@router.post("/{shipment_id}/scan")
async def scan_receiving(
    shipment_id: int,
    payload: ShipmentScanRequest,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    shipment = db.get(InvInboundShipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    event = InvReceivingScanEvent(shipment_id=shipment_id, user_id=user.id, **payload.model_dump())
    db.add(event)
    db.commit()
    await ws_manager.broadcast(
        f"receiving:{shipment_id}",
        {
            "event": "scan",
            "shipment_id": shipment_id,
            "scanned_code": payload.scanned_code,
            "result": payload.scan_result,
            "device_id": payload.device_id,
        },
    )
    return {"scan_event_id": event.id}


@router.post("/{shipment_id}/confirm-receipt")
async def confirm_receipt(
    shipment_id: int,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    shipment = db.get(InvInboundShipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    old_status = shipment.status
    shipment.status = "received"
    log_audit_event(
        db,
        actor_user_id=user.id,
        entity_type="inv_inbound_shipment",
        entity_id=str(shipment.id),
        action="confirm_receipt",
        before={"status": old_status},
        after={"status": shipment.status},
    )
    enqueue_outbox_event(
        db,
        event_name="inbound.received",
        aggregate_type="shipment",
        aggregate_id=str(shipment.id),
        payload={"shipment_id": shipment.id, "status": shipment.status},
    )
    db.commit()
    await ws_manager.broadcast(f"receiving:{shipment_id}", {"event": "receipt_confirmed", "shipment_id": shipment_id})
    return {"status": shipment.status}


@router.post("/{shipment_id}/discrepancies")
def create_discrepancy(
    shipment_id: int,
    payload: ShipmentDiscrepancyCreate,
    db: Session = Depends(get_db),
    user: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    shipment = db.get(InvInboundShipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    db.add(
        InvDiscrepancyReport(
            shipment_id=shipment_id,
            shipment_line_id=payload.shipment_line_id,
            issue_type=payload.issue_type,
            expected_qty=payload.expected_qty,
            received_qty=payload.received_qty,
            severity=payload.severity,
            notes=payload.notes,
            created_by=user.id,
        )
    )
    shipment.status = "discrepancy"
    db.commit()
    return {"status": "discrepancy_logged"}


@router.post("/{shipment_id}/lines")
def create_shipment_line(
    shipment_id: int,
    line: InboundShipmentLineCreate,
    db: Session = Depends(get_db),
    _: CoreUser = Depends(require_permission("purchase.write")),
) -> dict:
    shipment = db.get(InvInboundShipment, shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    record = InvInboundShipmentLine(shipment_id=shipment_id, **line.model_dump())
    db.add(record)
    db.commit()
    return {"id": record.id}
