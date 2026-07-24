"""initial schema — 12 tables per db_schema.md

Revision ID: 0001
Revises:
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# db_schema.md §0.3 — tables carrying sme_id-owned data get RLS (rule zero).
# smes is the tenant root (no sme_id); sessions/otp_challenges are pre-session
# by design (db_schema.md §1.2, §1.3) and explicitly excluded from RLS.
_RLS_TABLES = (
    "agents",
    "buyers",
    "conversations",
    "messages",
    "audit_entries",
    "excel_snapshots",
    "excel_stock_items",
    "order_intents",
    "qdrant_collection_registry",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE TABLE smes (
          id                uuid PRIMARY KEY,
          name              varchar(120) NOT NULL,
          owner_name        varchar(120) NOT NULL,
          owner_phone       varchar(20)  NOT NULL UNIQUE,
          city              varchar(60)  NOT NULL DEFAULT 'Karachi',
          segment           varchar(40)  NOT NULL DEFAULT 'textile',
          onboarded_at      timestamptz  NOT NULL DEFAULT now(),
          created_at        timestamptz  NOT NULL DEFAULT now(),
          updated_at        timestamptz  NOT NULL DEFAULT now(),

          CONSTRAINT owner_phone_e164 CHECK (owner_phone ~ '^\\+923[0-9]{9}$'),
          CONSTRAINT segment_check CHECK (segment IN ('textile', 'pharma', 'retail', 'other'))
        )
        """
    )
    op.execute("CREATE INDEX ix_smes_owner_phone ON smes (owner_phone)")

    op.execute(
        """
        CREATE TABLE sessions (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          cookie_hash       varchar(64) NOT NULL UNIQUE,
          expires_at        timestamptz NOT NULL,
          created_at        timestamptz NOT NULL DEFAULT now(),
          last_used_at      timestamptz NOT NULL DEFAULT now(),
          user_agent        text,
          ip_address        inet,

          CONSTRAINT expires_future CHECK (expires_at > created_at)
        )
        """
    )
    op.execute("CREATE INDEX ix_sessions_cookie_hash ON sessions (cookie_hash)")
    op.execute("CREATE INDEX ix_sessions_sme_id ON sessions (sme_id)")
    # db_schema.md §1.2 specifies "WHERE expires_at > now()" here, but Postgres
    # requires partial-index predicates to be IMMUTABLE — now() isn't, and can't
    # be (a partial index can't track a rolling "now"). Predicate dropped; callers
    # still filter expires_at > now() at query time, which a plain btree serves fine.
    op.execute("CREATE INDEX ix_sessions_expires ON sessions (expires_at)")

    op.execute(
        """
        CREATE TABLE otp_challenges (
          id                uuid PRIMARY KEY,
          phone             varchar(20) NOT NULL,
          otp_hash          varchar(64) NOT NULL,
          expires_at        timestamptz NOT NULL,
          attempts          smallint    NOT NULL DEFAULT 0,
          consumed_at       timestamptz,
          created_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT phone_e164 CHECK (phone ~ '^\\+923[0-9]{9}$'),
          CONSTRAINT attempts_ceiling CHECK (attempts <= 10)
        )
        """
    )
    # same IMMUTABLE issue as ix_sessions_expires above — now() dropped from the
    # predicate, consumed_at IS NULL is immutable so that half stays.
    op.execute(
        "CREATE INDEX ix_otp_phone_active ON otp_challenges (phone) WHERE consumed_at IS NULL"
    )

    op.execute(
        """
        CREATE TABLE agents (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          name              varchar(60) NOT NULL,
          name_urdu         varchar(60) NOT NULL,
          status            varchar(20) NOT NULL DEFAULT 'live',
          tool_bindings     jsonb       NOT NULL,
          system_prompt_key varchar(40) NOT NULL,
          created_at        timestamptz NOT NULL DEFAULT now(),
          updated_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT status_check CHECK (status IN ('live', 'paused'))
        )
        """
    )
    op.execute("CREATE INDEX ix_agents_sme_id ON agents (sme_id)")

    op.execute(
        """
        CREATE TABLE buyers (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          name              varchar(120) NOT NULL,
          phone             varchar(20),
          wa_id             varchar(80)  NOT NULL,
          first_seen_at     timestamptz  NOT NULL DEFAULT now(),
          last_seen_at      timestamptz  NOT NULL DEFAULT now(),
          created_at        timestamptz  NOT NULL DEFAULT now(),

          CONSTRAINT phone_e164_if_present CHECK (phone IS NULL OR phone ~ '^\\+923[0-9]{9}$')
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX ux_buyers_sme_wa_id ON buyers (sme_id, wa_id)")
    op.execute("CREATE INDEX ix_buyers_sme_last_seen ON buyers (sme_id, last_seen_at DESC)")

    op.execute(
        """
        CREATE TABLE excel_snapshots (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          snapshot_hash     varchar(64) NOT NULL,
          ingested_at       timestamptz NOT NULL DEFAULT now(),
          is_active         boolean     NOT NULL DEFAULT true,
          source_filename   varchar(200),
          created_at        timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_excel_active_per_sme ON excel_snapshots (sme_id) "
        "WHERE is_active = true"
    )
    op.execute("CREATE INDEX ix_excel_sme_id ON excel_snapshots (sme_id, ingested_at DESC)")

    op.execute(
        """
        CREATE TABLE excel_stock_items (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          snapshot_id       uuid NOT NULL REFERENCES excel_snapshots(id) ON DELETE CASCADE,
          sku_canonical     varchar(80)    NOT NULL,
          sku_aliases       text[]         NOT NULL DEFAULT '{}',
          stock             integer        NOT NULL,
          unit              varchar(20)    NOT NULL DEFAULT 'pieces',
          price_per_unit    numeric(12,2)  NOT NULL,
          price_currency    varchar(3)     NOT NULL DEFAULT 'PKR',
          reorder_threshold integer        NOT NULL DEFAULT 0,
          created_at        timestamptz    NOT NULL DEFAULT now(),

          CONSTRAINT stock_nonneg CHECK (stock >= 0),
          CONSTRAINT price_nonneg CHECK (price_per_unit >= 0),
          CONSTRAINT unit_check CHECK (unit IN ('pieces', 'meters', 'kg', 'liters', 'boxes'))
        )
        """
    )
    op.execute("CREATE INDEX ix_stock_sme_sku ON excel_stock_items (sme_id, sku_canonical)")
    op.execute("CREATE INDEX ix_stock_sme_snapshot ON excel_stock_items (sme_id, snapshot_id)")
    op.execute(
        "CREATE INDEX ix_stock_sku_gin ON excel_stock_items USING gin (sku_canonical gin_trgm_ops)"
    )

    op.execute(
        """
        CREATE TABLE qdrant_collection_registry (
          sme_id            uuid PRIMARY KEY REFERENCES smes(id) ON DELETE CASCADE,
          collection_name   varchar(120) NOT NULL UNIQUE,
          embedding_model   varchar(80)  NOT NULL,
          dimension         integer      NOT NULL,
          created_at        timestamptz  NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE conversations (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          agent_id          uuid NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
          buyer_id          uuid NOT NULL REFERENCES buyers(id) ON DELETE RESTRICT,
          channel           varchar(20) NOT NULL DEFAULT 'widget',
          last_message_at   timestamptz NOT NULL DEFAULT now(),
          is_unread         boolean     NOT NULL DEFAULT false,
          is_flagged        boolean     NOT NULL DEFAULT false,
          flag_reason       varchar(500),
          created_at        timestamptz NOT NULL DEFAULT now(),
          updated_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT channel_check CHECK (channel IN ('widget', 'whatsapp'))
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_convo_sme_buyer_agent ON conversations (sme_id, buyer_id, agent_id)"
    )
    op.execute(
        "CREATE INDEX ix_convo_sme_last_message ON conversations (sme_id, last_message_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_convo_sme_unread ON conversations (sme_id) WHERE is_unread = true"
    )
    op.execute(
        "CREATE INDEX ix_convo_sme_flagged ON conversations (sme_id) WHERE is_flagged = true"
    )
    op.execute("CREATE INDEX ix_convo_sme_channel ON conversations (sme_id, channel)")

    op.execute(
        """
        CREATE TABLE messages (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          sender            varchar(10) NOT NULL,
          text              text        NOT NULL,
          text_original     text,
          timestamp_ts      timestamptz NOT NULL DEFAULT now(),
          is_pending        boolean     NOT NULL DEFAULT false,
          audit_entry_id    uuid,
          created_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT sender_check CHECK (sender IN ('buyer', 'agent')),
          CONSTRAINT text_length CHECK (char_length(text) BETWEEN 1 AND 4096),
          CONSTRAINT pending_only_for_buyer CHECK (
            NOT (is_pending = true AND sender = 'agent')
          ),
          CONSTRAINT audit_only_for_agent CHECK (
            NOT (audit_entry_id IS NOT NULL AND sender = 'buyer')
          )
        )
        """
    )
    op.execute("CREATE INDEX ix_msg_convo_ts ON messages (conversation_id, timestamp_ts ASC)")
    op.execute("CREATE INDEX ix_msg_sme_ts ON messages (sme_id, timestamp_ts DESC)")
    op.execute("CREATE INDEX ix_msg_sme_id_id ON messages (sme_id, id)")

    op.execute(
        """
        CREATE TABLE audit_entries (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          message_id        uuid NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
          buyer_message_id  uuid NOT NULL REFERENCES messages(id) ON DELETE RESTRICT,
          parsed_intent     text        NOT NULL,
          tool_calls        jsonb       NOT NULL,
          agent_reply_text  text        NOT NULL,
          model             varchar(80) NOT NULL,
          total_latency_ms  integer     NOT NULL,
          created_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT tool_calls_is_array CHECK (jsonb_typeof(tool_calls) = 'array')
        )
        """
    )
    op.execute("CREATE INDEX ix_audit_sme ON audit_entries (sme_id, created_at DESC)")
    op.execute("CREATE INDEX ix_audit_message_id ON audit_entries (message_id)")

    op.execute(
        """
        CREATE TABLE order_intents (
          id                uuid PRIMARY KEY,
          sme_id            uuid NOT NULL REFERENCES smes(id) ON DELETE CASCADE,
          buyer_id          uuid NOT NULL REFERENCES buyers(id) ON DELETE RESTRICT,
          conversation_id   uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          message_id        uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
          idempotency_key   varchar(80) NOT NULL,
          sku_canonical     varchar(80) NOT NULL,
          quantity          integer     NOT NULL,
          agreed_price_per_unit numeric(12,2) NOT NULL,
          total_amount      numeric(14,2) GENERATED ALWAYS AS (quantity * agreed_price_per_unit) STORED,
          delivery_date     date        NOT NULL,
          notes             varchar(500),
          created_at        timestamptz NOT NULL DEFAULT now(),

          CONSTRAINT qty_positive CHECK (quantity > 0),
          CONSTRAINT price_positive CHECK (agreed_price_per_unit > 0)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX ux_order_intents_idem ON order_intents (sme_id, idempotency_key)"
    )
    op.execute(
        "CREATE INDEX ix_order_intents_sme_created ON order_intents (sme_id, created_at DESC)"
    )
    op.execute("CREATE INDEX ix_order_intents_buyer ON order_intents (sme_id, buyer_id)")

    for table in _RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_sme_isolation ON {table} "
            f"USING (sme_id = current_setting('app.current_sme_id')::uuid)"
        )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
            CREATE ROLE app_role LOGIN;
          END IF;
        END $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO app_role")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role")


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_role")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_role")
    op.execute("DROP ROLE IF EXISTS app_role")

    for table in (
        "order_intents",
        "audit_entries",
        "messages",
        "conversations",
        "qdrant_collection_registry",
        "excel_stock_items",
        "excel_snapshots",
        "buyers",
        "agents",
        "otp_challenges",
        "sessions",
        "smes",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
