# api/app/crud/crud_reservation.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException, status

from app.crud.base import CRUDBase
from app.models.reservation import Reservation
from app.models.user import User
from app.models.table import Table
from app.schemas.enums import TableStatus
from app.schemas.reservation import ReservationCreate, ReservationUpdate

class CRUDReservation(CRUDBase[Reservation, ReservationCreate, ReservationUpdate]):
    async def get_reservations_by_date_range(
        self, db: AsyncSession, *, start_date: datetime, end_date: datetime, current_user: User
    ) -> List[Reservation]:
        """
        Busca todas as reservas para a loja do usuário dentro de um intervalo de datas.
        """
        stmt = (
            select(self.model)
            .where(
                self.model.store_id == current_user.store_id,
                self.model.reservation_time >= start_date,
                self.model.reservation_time <= end_date,
            )
            .options(selectinload(self.model.table))
            .order_by(self.model.reservation_time)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: ReservationCreate, current_user: User) -> Reservation:
        """
        Cria uma nova reserva e atualiza o status da mesa para 'reservada'.
        """
        table = await db.get(Table, obj_in.table_id)
        if not table or table.store_id != current_user.store_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mesa não encontrada ou não pertence a esta loja."
            )
        
        if table.status != TableStatus.AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A mesa {table.number} não está disponível para reserva."
            )
            
        table.status = TableStatus.RESERVED
        db.add(table)
        
        db_obj = await super().create(db=db, obj_in=obj_in, current_user=current_user)
        
        await db.refresh(db_obj, attribute_names=["table"])
        
        return db_obj

    async def remove(self, db: AsyncSession, *, id: int, current_user: User) -> Optional[Reservation]:
        """
        Remove uma reserva e atualiza o status da mesa de volta para 'disponível'.
        """
        stmt = select(self.model).where(self.model.id == id).options(selectinload(self.model.table))
        result = await db.execute(stmt)
        db_obj = result.scalars().first()

        if db_obj:
            if db_obj.store_id != current_user.store_id:
                return None

            if db_obj.table:
                db_obj.table.status = TableStatus.AVAILABLE
                db.add(db_obj.table)

            await db.delete(db_obj)
            await db.commit()
        
        return db_obj

reservation = CRUDReservation(Reservation)