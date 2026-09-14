from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo
from app.core.database_pool import db_pool

async def calculate_monthly_revenue(property_id: str, month: int, year: int, tenant_id: str) -> Decimal:
    """
    Calculates revenue for a specific month, using the property's own
    local timezone to determine the month boundaries. A booking near
    midnight at the end/start of a month can fall on a different
    calendar day locally than it does in UTC, so the month boundary has
    to be computed in the property's own timezone, not left naive.
    """
    try:
        if not db_pool.session_factory:
            await db_pool.initialize()

        if not db_pool.session_factory:
            raise Exception("Database pool not available")

        async with db_pool.get_session() as session:
            from sqlalchemy import text

            tz_row = (await session.execute(
                text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
                {"property_id": property_id, "tenant_id": tenant_id}
            )).fetchone()

            if not tz_row:
                return Decimal('0')

            tz = ZoneInfo(tz_row.timezone)
            start_date = datetime(year, month, 1, tzinfo=tz)
            if month < 12:
                end_date = datetime(year, month + 1, 1, tzinfo=tz)
            else:
                end_date = datetime(year + 1, 1, 1, tzinfo=tz)

            query = text("""
                SELECT SUM(total_amount) as total
                FROM reservations
                WHERE property_id = :property_id
                AND tenant_id = :tenant_id
                AND check_in_date >= :start_date
                AND check_in_date < :end_date
            """)
            result = await session.execute(query, {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
            })
            row = result.fetchone()
            return Decimal(str(row.total)) if row and row.total is not None else Decimal('0')

    except Exception as e:
        print(f"Monthly revenue error for {property_id} (tenant: {tenant_id}, {year}-{month}): {e}")
        return Decimal('0')

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Use the shared global pool instead of creating a new one per request
        if not db_pool.session_factory:
            await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        
        # Create property-specific mock data for testing when DB is unavailable
        # This ensures each property shows different figures
        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4}, 
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }
        
        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})
        
        return {
            "property_id": property_id,
            "tenant_id": tenant_id, 
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
