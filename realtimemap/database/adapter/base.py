from abc import ABC, abstractmethod
from typing import Union, Optional, List, Dict, Any, Generic

from my_type import Model, CreateSchema, UpdateSchema


class BaseAdapter(ABC, Generic[Model, CreateSchema, UpdateSchema]):
    """
    Base adapter interface defining the contract for all database adapters.
    All database-specific adapters must implement these methods.
    """

    @abstractmethod
    async def create(self, data: CreateSchema, **kwargs: Any) -> Model:
        """
        Create a new record in the database.

        Args:
            data: Schema containing the data to create
            **kwargs: Additional fields to include in the record

        Returns:
            The created model instance

        Raises:
            IntegrityError: If the record violates database constraints
            ServerError: If any other error occurs during creation
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, item_id: Any, data: UpdateSchema) -> Optional[Model]:
        """
        Update an existing record in the database.

        Args:
            item_id: ID of the record to update
            data: Schema containing the fields to update

        Returns:
            The updated model instance, or None if record not found

        Raises:
            ServerError: If an error occurs during update
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(
        self,
        item_id: Any,
        join_related: Optional[Union[List[str], Dict[str, Any]]] = None,
        load_strategy: Any = None,
    ) -> Optional[Model]:
        """
        Retrieve a record by its ID.

        Args:
            item_id: ID of the record to retrieve
            join_related: Optional list of relationships to load, or dict mapping
                         relationships to load strategies
            load_strategy: Strategy to use for loading relationships (e.g., joinedload)

        Returns:
            The model instance if found, None otherwise
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, record_id: Any) -> Optional[Model]:
        """
        Delete a record from the database.

        Args:
            record_id: ID of the record to delete

        Returns:
            The deleted model instance if found and deleted, None otherwise
        """
        raise NotImplementedError

    @abstractmethod
    async def exist(self, record_id: Any, id_field: Optional[str] = None) -> bool:
        """
        Check if a record exists in the database.

        Args:
            id_field: Field to check
            record_id: ID of the record to check

        Returns:
            True if the record exists, False otherwise
        """
        raise NotImplementedError
