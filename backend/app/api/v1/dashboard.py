from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from app.services.cache import get_revenue_summary
from app.services.reservations import calculate_monthly_revenue
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = getattr(current_user, "tenant_id", "default_tenant") or "default_tenant"

    # Optional month/year scoping, using the property's own timezone for the
    # month boundary (see calculate_monthly_revenue). Falls back to the
    # existing lifetime-total behavior when no month/year is given.
    if month is not None and year is not None:
        monthly_total = await calculate_monthly_revenue(property_id, month, year, tenant_id)
        return {
            "property_id": property_id,
            "total_revenue": float(monthly_total),
            "currency": "USD",
            "month": month,
            "year": year,
        }

    revenue_data = await get_revenue_summary(property_id, tenant_id)

    total_revenue_float = float(revenue_data['total'])

    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
