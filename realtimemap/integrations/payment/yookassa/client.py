import logging
import uuid
from decimal import Decimal
from typing import Optional, Dict, Any

from yookassa import Payment

from errors.http2 import GateWayError
from .schemas import CreatePayment, AmountPayment, ConfirmationPayment

logger = logging.getLogger(__name__)


class YookassaClient:
    @staticmethod
    def _preparate_data(
        value: Decimal,
        redirect_url: str,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        valid_data = CreatePayment(
            amount=AmountPayment(value=value, currency="RUB"),
            confirmation=ConfirmationPayment(return_url=redirect_url, type="redirect"),
            description=description,
            metadata=metadata,
            capture=True,
        )
        return valid_data

    @staticmethod
    def create_payment(payment_request: CreatePayment):
        try:
            payment = Payment.create(
                payment_request.model_dump(exclude_none=True), uuid.uuid4()
            )
            return payment
        except Exception as e:
            logger.error("Yokassa payment failed", e)
            raise GateWayError()
