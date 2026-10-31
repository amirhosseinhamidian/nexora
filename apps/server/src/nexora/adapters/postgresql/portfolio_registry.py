from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from nexora.adapters.postgresql.models import (
    AccountRecord,
    AssetIdentifierRecord,
    AssetRecord,
    PortfolioRecord,
)
from nexora.portfolio_registry import (
    AccountKind,
    AccountView,
    AssetClass,
    AssetIdentifierScheme,
    AssetIdentifierView,
    AssetView,
    PortfolioKind,
    PortfolioView,
    RegistryConflict,
    RegistryNotFound,
    RegistryStatus,
    normalize_asset_symbol,
    normalize_identifier,
    normalize_name,
    normalize_registry_key,
)


def _portfolio_view(record: PortfolioRecord) -> PortfolioView:
    return PortfolioView(
        portfolio_id=record.portfolio_id,
        portfolio_key=record.portfolio_key,
        name=record.name,
        kind=PortfolioKind(record.kind),
        base_asset_id=record.base_asset_id,
        status=RegistryStatus(record.status),
        row_version=record.row_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        archived_at=record.archived_at,
    )


def _asset_view(record: AssetRecord) -> AssetView:
    return AssetView(
        asset_id=record.asset_id,
        asset_key=record.asset_key,
        symbol=record.symbol,
        name=record.name,
        asset_class=AssetClass(record.asset_class),
        precision=record.precision,
        status=RegistryStatus(record.status),
        row_version=record.row_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        deactivated_at=record.deactivated_at,
    )


def _identifier_view(record: AssetIdentifierRecord) -> AssetIdentifierView:
    return AssetIdentifierView(
        asset_identifier_id=record.asset_identifier_id,
        asset_id=record.asset_id,
        scheme=AssetIdentifierScheme(record.scheme),
        value=record.value,
        is_primary=record.is_primary,
        created_at=record.created_at,
    )


def _account_view(record: AccountRecord) -> AccountView:
    return AccountView(
        account_id=record.account_id,
        portfolio_id=record.portfolio_id,
        account_key=record.account_key,
        name=record.name,
        kind=AccountKind(record.kind),
        institution_name=record.institution_name,
        external_reference=record.external_reference,
        status=RegistryStatus(record.status),
        row_version=record.row_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
        closed_at=record.closed_at,
    )


class PortfolioRegistryRepository:
    """Owner-scoped registry persistence with no destructive delete operation."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_asset(
        self,
        *,
        owner_id: UUID,
        asset_key: str,
        symbol: str,
        name: str,
        asset_class: AssetClass,
        precision: int,
    ) -> AssetView:
        if not 0 <= precision <= 30:
            raise ValueError("asset precision must be between 0 and 30")
        record = AssetRecord(
            asset_id=uuid4(),
            owner_id=owner_id,
            asset_key=normalize_registry_key(asset_key),
            symbol=normalize_asset_symbol(symbol),
            name=normalize_name(name),
            asset_class=asset_class.value,
            precision=precision,
            status=RegistryStatus.ACTIVE.value,
            row_version=1,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(record)
                session.flush()
        except IntegrityError as error:
            raise RegistryConflict("asset key or identity already exists for owner") from error
        return _asset_view(record)

    def list_assets(self, *, owner_id: UUID) -> tuple[AssetView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(AssetRecord)
                .where(AssetRecord.owner_id == owner_id)
                .order_by(AssetRecord.asset_key, AssetRecord.asset_id)
            ).all()
            return tuple(_asset_view(record) for record in records)

    def get_asset(self, *, owner_id: UUID, asset_id: UUID) -> AssetView:
        with self._session_factory() as session:
            record = session.scalar(
                select(AssetRecord).where(AssetRecord.owner_id == owner_id, AssetRecord.asset_id == asset_id)
            )
            if record is None:
                raise RegistryNotFound("asset is unavailable")
            return _asset_view(record)

    def add_asset_identifier(
        self,
        *,
        owner_id: UUID,
        asset_id: UUID,
        scheme: AssetIdentifierScheme,
        value: str,
        is_primary: bool,
    ) -> AssetIdentifierView:
        record = AssetIdentifierRecord(
            asset_identifier_id=uuid4(),
            owner_id=owner_id,
            asset_id=asset_id,
            scheme=scheme.value,
            value=normalize_identifier(value),
            is_primary=is_primary,
        )
        try:
            with self._session_factory.begin() as session:
                if (
                    session.scalar(
                        select(AssetRecord.asset_id).where(
                            AssetRecord.owner_id == owner_id,
                            AssetRecord.asset_id == asset_id,
                        )
                    )
                    is None
                ):
                    raise RegistryNotFound("asset is unavailable")
                session.add(record)
                session.flush()
        except IntegrityError as error:
            raise RegistryConflict("asset identifier already exists for owner") from error
        return _identifier_view(record)

    def deactivate_asset(
        self,
        *,
        owner_id: UUID,
        asset_id: UUID,
        expected_row_version: int,
    ) -> AssetView:
        observed_at = datetime.now(UTC)
        with self._session_factory.begin() as session:
            changed = session.execute(
                update(AssetRecord)
                .where(
                    AssetRecord.owner_id == owner_id,
                    AssetRecord.asset_id == asset_id,
                    AssetRecord.status == RegistryStatus.ACTIVE.value,
                    AssetRecord.row_version == expected_row_version,
                )
                .values(
                    status=RegistryStatus.INACTIVE.value,
                    deactivated_at=observed_at,
                    updated_at=observed_at,
                    row_version=AssetRecord.row_version + 1,
                )
                .returning(AssetRecord)
            ).scalar_one_or_none()
            if changed is not None:
                return _asset_view(changed)
            self._raise_asset_mutation_error(session, owner_id, asset_id)
        raise AssertionError("unreachable")

    def create_portfolio(
        self,
        *,
        owner_id: UUID,
        portfolio_key: str,
        name: str,
        kind: PortfolioKind,
        base_asset_id: UUID,
    ) -> PortfolioView:
        record = PortfolioRecord(
            portfolio_id=uuid4(),
            owner_id=owner_id,
            portfolio_key=normalize_registry_key(portfolio_key),
            name=normalize_name(name),
            kind=kind.value,
            base_asset_id=base_asset_id,
            status=RegistryStatus.ACTIVE.value,
            row_version=1,
        )
        try:
            with self._session_factory.begin() as session:
                active_asset = session.scalar(
                    select(AssetRecord.asset_id).where(
                        AssetRecord.owner_id == owner_id,
                        AssetRecord.asset_id == base_asset_id,
                        AssetRecord.status == RegistryStatus.ACTIVE.value,
                    )
                )
                if active_asset is None:
                    raise RegistryNotFound("base asset is unavailable or inactive")
                session.add(record)
                session.flush()
        except IntegrityError as error:
            raise RegistryConflict("portfolio key already exists for owner") from error
        return _portfolio_view(record)

    def list_portfolios(self, *, owner_id: UUID) -> tuple[PortfolioView, ...]:
        with self._session_factory() as session:
            records = session.scalars(
                select(PortfolioRecord)
                .where(PortfolioRecord.owner_id == owner_id)
                .order_by(PortfolioRecord.portfolio_key, PortfolioRecord.portfolio_id)
            ).all()
            return tuple(_portfolio_view(record) for record in records)

    def get_portfolio(self, *, owner_id: UUID, portfolio_id: UUID) -> PortfolioView:
        with self._session_factory() as session:
            record = session.scalar(
                select(PortfolioRecord).where(
                    PortfolioRecord.owner_id == owner_id,
                    PortfolioRecord.portfolio_id == portfolio_id,
                )
            )
            if record is None:
                raise RegistryNotFound("portfolio is unavailable")
            return _portfolio_view(record)

    def archive_portfolio(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        expected_row_version: int,
    ) -> PortfolioView:
        observed_at = datetime.now(UTC)
        with self._session_factory.begin() as session:
            changed = session.execute(
                update(PortfolioRecord)
                .where(
                    PortfolioRecord.owner_id == owner_id,
                    PortfolioRecord.portfolio_id == portfolio_id,
                    PortfolioRecord.status == RegistryStatus.ACTIVE.value,
                    PortfolioRecord.row_version == expected_row_version,
                )
                .values(
                    status=RegistryStatus.ARCHIVED.value,
                    archived_at=observed_at,
                    updated_at=observed_at,
                    row_version=PortfolioRecord.row_version + 1,
                )
                .returning(PortfolioRecord)
            ).scalar_one_or_none()
            if changed is not None:
                return _portfolio_view(changed)
            self._raise_portfolio_mutation_error(session, owner_id, portfolio_id)
        raise AssertionError("unreachable")

    def create_account(
        self,
        *,
        owner_id: UUID,
        portfolio_id: UUID,
        account_key: str,
        name: str,
        kind: AccountKind,
        institution_name: str | None = None,
        external_reference: str | None = None,
    ) -> AccountView:
        institution = normalize_name(institution_name) if institution_name is not None else None
        reference = external_reference.strip() if external_reference is not None else None
        if reference is not None and (not reference or len(reference) > 160):
            raise ValueError("external reference must contain 1-160 characters")
        record = AccountRecord(
            account_id=uuid4(),
            owner_id=owner_id,
            portfolio_id=portfolio_id,
            account_key=normalize_registry_key(account_key),
            name=normalize_name(name),
            kind=kind.value,
            institution_name=institution,
            external_reference=reference,
            status=RegistryStatus.ACTIVE.value,
            row_version=1,
        )
        try:
            with self._session_factory.begin() as session:
                portfolio = session.scalar(
                    select(PortfolioRecord.portfolio_id).where(
                        PortfolioRecord.owner_id == owner_id,
                        PortfolioRecord.portfolio_id == portfolio_id,
                        PortfolioRecord.status == RegistryStatus.ACTIVE.value,
                    )
                )
                if portfolio is None:
                    raise RegistryNotFound("portfolio is unavailable or archived")
                session.add(record)
                session.flush()
        except IntegrityError as error:
            raise RegistryConflict("account key already exists for owner") from error
        return _account_view(record)

    def list_accounts(self, *, owner_id: UUID, portfolio_id: UUID | None = None) -> tuple[AccountView, ...]:
        statement = select(AccountRecord).where(AccountRecord.owner_id == owner_id)
        if portfolio_id is not None:
            statement = statement.where(AccountRecord.portfolio_id == portfolio_id)
        with self._session_factory() as session:
            records = session.scalars(statement.order_by(AccountRecord.account_key, AccountRecord.account_id)).all()
            return tuple(_account_view(record) for record in records)

    def close_account(
        self,
        *,
        owner_id: UUID,
        account_id: UUID,
        expected_row_version: int,
    ) -> AccountView:
        observed_at = datetime.now(UTC)
        with self._session_factory.begin() as session:
            changed = session.execute(
                update(AccountRecord)
                .where(
                    AccountRecord.owner_id == owner_id,
                    AccountRecord.account_id == account_id,
                    AccountRecord.status == RegistryStatus.ACTIVE.value,
                    AccountRecord.row_version == expected_row_version,
                )
                .values(
                    status=RegistryStatus.CLOSED.value,
                    closed_at=observed_at,
                    updated_at=observed_at,
                    row_version=AccountRecord.row_version + 1,
                )
                .returning(AccountRecord)
            ).scalar_one_or_none()
            if changed is not None:
                return _account_view(changed)
            record = session.scalar(
                select(AccountRecord).where(
                    AccountRecord.owner_id == owner_id,
                    AccountRecord.account_id == account_id,
                )
            )
            if record is None:
                raise RegistryNotFound("account is unavailable")
            raise RegistryConflict("account lifecycle or row version changed")

    @staticmethod
    def _raise_asset_mutation_error(session: Session, owner_id: UUID, asset_id: UUID) -> None:
        record = session.scalar(
            select(AssetRecord).where(AssetRecord.owner_id == owner_id, AssetRecord.asset_id == asset_id)
        )
        if record is None:
            raise RegistryNotFound("asset is unavailable")
        raise RegistryConflict("asset lifecycle or row version changed")

    @staticmethod
    def _raise_portfolio_mutation_error(session: Session, owner_id: UUID, portfolio_id: UUID) -> None:
        record = session.scalar(
            select(PortfolioRecord).where(
                PortfolioRecord.owner_id == owner_id,
                PortfolioRecord.portfolio_id == portfolio_id,
            )
        )
        if record is None:
            raise RegistryNotFound("portfolio is unavailable")
        raise RegistryConflict("portfolio lifecycle or row version changed")
