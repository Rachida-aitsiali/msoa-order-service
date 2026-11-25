import os

import grpc

import inventory_pb2
import inventory_pb2_grpc

GRPC_ADDRESS = os.getenv("INVENTORY_GRPC_ADDRESS", "localhost:50051")
TIMEOUT_SECONDS = float(os.getenv("INVENTORY_GRPC_TIMEOUT", "2"))

_channel = grpc.insecure_channel(GRPC_ADDRESS)
_stub = inventory_pb2_grpc.InventoryServiceStub(_channel)


def check_availability(product_id, quantity):
    """Retourne (available, availableQuantity).

    ValueError : produit inconnu ou requete invalide
    ConnectionError : Inventory injoignable ou trop lent
    """
    request = inventory_pb2.AvailabilityRequest(
        productId=str(product_id), quantity=int(quantity)
    )
    try:
        response = _stub.CheckAvailability(request, timeout=TIMEOUT_SECONDS)
    except grpc.RpcError as e:
        code = e.code()
        if code == grpc.StatusCode.NOT_FOUND:
            raise ValueError(f"Product {product_id} not found.")
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise ValueError(e.details() or "Invalid availability request.")
        raise ConnectionError(f"Inventory gRPC error: {code.name}")
    return response.available, response.availableQuantity