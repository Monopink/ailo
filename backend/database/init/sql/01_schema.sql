--
-- PostgreSQL database dump
--

\restrict says123

-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.3 (Debian 18.3-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA public;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: calculate_memory_expires_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_memory_expires_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.memory_type = 'recent' THEN
        NEW.expires_at := COALESCE(NEW.refreshed_at, NEW.created_at) +
                         (NEW.importance * INTERVAL '10 days');
    ELSE
        NEW.expires_at := NULL;  -- core memories never expire
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: prevent_square_category_key_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_square_category_key_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.category_key <> OLD.category_key THEN
                RAISE EXCEPTION 'square_categories.category_key is immutable';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admin_login_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_login_logs (
    id integer NOT NULL,
    admin_user_id integer,
    username character varying(50) NOT NULL,
    user_agent text,
    ip_address inet,
    result integer NOT NULL,
    fail_reason character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: admin_login_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_login_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_login_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_login_logs_id_seq OWNED BY public.admin_login_logs.id;


--
-- Name: admin_operation_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_operation_logs (
    id integer NOT NULL,
    admin_user_id integer NOT NULL,
    operation_type integer NOT NULL,
    resource_type character varying(50) NOT NULL,
    resource_id character varying(100),
    resource_name character varying(255),
    operation_desc text NOT NULL,
    ip_address inet,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: admin_operation_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_operation_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_operation_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_operation_logs_id_seq OWNED BY public.admin_operation_logs.id;


--
-- Name: admin_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admin_users (
    id integer NOT NULL,
    username character varying(50) NOT NULL,
    password_hash character varying(255) NOT NULL,
    role integer NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    last_login timestamp with time zone,
    login_count integer DEFAULT 0 NOT NULL,
    created_by integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: admin_users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.admin_users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: admin_users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.admin_users_id_seq OWNED BY public.admin_users.id;


--
-- Name: ai_buffer_wake_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_buffer_wake_events (
    id bigint NOT NULL,
    buffer_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    event_time_ms bigint NOT NULL,
    reason character varying(32) NOT NULL,
    trigger_message_type smallint NOT NULL,
    prev_wake_delay_ms integer,
    new_wake_delay_ms integer,
    micro_expires_at_ms bigint,
    macro_expires_at_ms bigint,
    buffer_expires_at_ms bigint,
    adjustment_mode character varying(32) NOT NULL,
    wake_time_min_ms integer NOT NULL,
    wake_time_max_ms integer NOT NULL,
    wake_time_bias character varying(32) NOT NULL,
    random_number integer,
    wake_adjustment_count_after smallint NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_buffer_wake_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_buffer_wake_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_buffer_wake_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_buffer_wake_events_id_seq OWNED BY public.ai_buffer_wake_events.id;


--
-- Name: ai_conversation_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_conversation_items (
    id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    role character varying(20) NOT NULL,
    message_type character varying(20) DEFAULT 'text'::character varying NOT NULL,
    text_content text,
    media_url text,
    media_metadata jsonb,
    client_msg_ids text[] DEFAULT '{}'::text[] NOT NULL,
    buffer_id bigint,
    is_excluded_from_context smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ai_conversation_items_content CHECK (((((message_type)::text = 'text'::text) AND (text_content IS NOT NULL) AND (media_url IS NULL)) OR (((message_type)::text = ANY (ARRAY[('image'::character varying)::text, ('audio'::character varying)::text])) AND (media_url IS NOT NULL)))),
    CONSTRAINT ck_ai_conversation_items_user_buffer CHECK (((((role)::text = 'user'::text) AND (buffer_id IS NOT NULL)) OR ((role)::text <> 'user'::text)))
);


--
-- Name: COLUMN ai_conversation_items.media_metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items.media_metadata IS 'Media metadata (dimensions, duration, transcript, etc.)';


--
-- Name: COLUMN ai_conversation_items.buffer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items.buffer_id IS 'Associated buffer ID (references ai_message_buffer.id, no FK constraint)';


--
-- Name: COLUMN ai_conversation_items.is_excluded_from_context; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items.is_excluded_from_context IS 'Context status enum: 0=included, 1=excluded';


--
-- Name: ai_conversation_items_archive; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_conversation_items_archive (
    id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    role character varying(20) NOT NULL,
    message_type character varying(20) DEFAULT 'text'::character varying NOT NULL,
    text_content text,
    media_url text,
    media_metadata jsonb,
    client_msg_ids text[] DEFAULT '{}'::text[] NOT NULL,
    buffer_id bigint,
    is_excluded_from_context smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone NOT NULL,
    archived_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN ai_conversation_items_archive.media_metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items_archive.media_metadata IS 'Media metadata (dimensions, duration, transcript, etc.)';


--
-- Name: COLUMN ai_conversation_items_archive.buffer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items_archive.buffer_id IS 'Associated buffer ID (references ai_message_buffer.id, no FK constraint)';


--
-- Name: COLUMN ai_conversation_items_archive.is_excluded_from_context; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_items_archive.is_excluded_from_context IS 'Context status enum: 0=included, 1=excluded';


--
-- Name: ai_conversation_runtime; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_conversation_runtime (
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    ingress_version bigint DEFAULT 0 NOT NULL,
    active_turn_version bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE ai_conversation_runtime; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_conversation_runtime IS 'AI conversation runtime turn versions for delayed preemption';


--
-- Name: COLUMN ai_conversation_runtime.ingress_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_runtime.ingress_version IS 'Inbound version incremented on each content input';


--
-- Name: COLUMN ai_conversation_runtime.active_turn_version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_runtime.active_turn_version IS 'Active processing version switched on new locked window';


--
-- Name: ai_conversation_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_conversation_state (
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    pending_messages jsonb,
    interrupted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE ai_conversation_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_conversation_state IS 'AI conversation state - tracks pending messages and interruption state';


--
-- Name: COLUMN ai_conversation_state.pending_messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_state.pending_messages IS 'Pending outgoing payload {"outgoing":[...],"total_pending":N}';


--
-- Name: COLUMN ai_conversation_state.interrupted_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_conversation_state.interrupted_at IS 'Timestamp when conversation was interrupted by user message';


--
-- Name: ai_dimension_relationship_mappings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_dimension_relationship_mappings (
    id integer NOT NULL,
    dimension_id integer NOT NULL,
    start_position integer NOT NULL,
    end_position integer NOT NULL,
    relationship_id integer NOT NULL,
    priority integer DEFAULT 1 NOT NULL,
    limit_count integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_dimension_relationship_mappings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_dimension_relationship_mappings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_dimension_relationship_mappings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_dimension_relationship_mappings_id_seq OWNED BY public.ai_dimension_relationship_mappings.id;


--
-- Name: ai_dimensions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_dimensions (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100),
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_dimensions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_dimensions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_dimensions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_dimensions_id_seq OWNED BY public.ai_dimensions.id;


--
-- Name: ai_instance_dimensions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_instance_dimensions (
    id bigint NOT NULL,
    instance_id bigint NOT NULL,
    dimension_id integer NOT NULL,
    score integer NOT NULL,
    "position" integer NOT NULL,
    position_mapping_algorithm integer DEFAULT 1,
    position_mapping_params jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_instance_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_instance_memories (
    id bigint NOT NULL,
    instance_id bigint NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    memory_type character varying(20) NOT NULL,
    content text NOT NULL,
    importance integer DEFAULT 5 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    refreshed_at timestamp with time zone,
    expires_at timestamp with time zone,
    source_message_id bigint,
    status integer DEFAULT 1 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ai_instance_memories_importance CHECK (((importance >= 1) AND (importance <= 10))),
    CONSTRAINT ck_ai_instance_memories_status CHECK ((status = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_ai_instance_memories_type CHECK (((memory_type)::text = ANY (ARRAY[('core'::character varying)::text, ('recent'::character varying)::text])))
);


--
-- Name: TABLE ai_instance_memories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_instance_memories IS 'AI instance memories - manages AI memories about users with importance-based lifetime';


--
-- Name: COLUMN ai_instance_memories.memory_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.memory_type IS 'Memory type: core (permanent), recent (will fade)';


--
-- Name: COLUMN ai_instance_memories.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.content IS 'Memory content - concise one-sentence description';


--
-- Name: COLUMN ai_instance_memories.importance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.importance IS 'Importance level 1-10, determines lifetime (importance 脳 10 = days)';


--
-- Name: COLUMN ai_instance_memories.refreshed_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.refreshed_at IS 'AI refresh timestamp, resets lifetime if not NULL';


--
-- Name: COLUMN ai_instance_memories.expires_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.expires_at IS 'Pre-calculated expiration timestamp (auto-computed by trigger for recent memories)';


--
-- Name: COLUMN ai_instance_memories.source_message_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.source_message_id IS 'Source message ID that triggered this memory creation (for traceability)';


--
-- Name: COLUMN ai_instance_memories.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instance_memories.status IS 'Status: 1=active, 2=archived (forgotten)';


--
-- Name: ai_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_instances (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    qiao_id character varying(32) NOT NULL,
    creation_metadata jsonb NOT NULL,
    style_id integer NOT NULL,
    personality_id integer NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    prompt_variables jsonb,
    relationship_id integer,
    relationship_counts jsonb,
    request_params jsonb,
    llm_config_id integer,
    typing_speed_wpm integer NOT NULL,
    timezone character varying(50) DEFAULT 'Asia/Shanghai'::character varying NOT NULL,
    created_by integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    persona_id bigint
);


--
-- Name: TABLE ai_instances; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_instances IS 'AI instances - created when users add personas';


--
-- Name: COLUMN ai_instances.user_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.user_id IS 'Owning user ID (each row belongs to exactly one user)';


--
-- Name: COLUMN ai_instances.user_qiao_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.user_qiao_id IS 'Owning user qiao_id (redundant for query convenience)';


--
-- Name: COLUMN ai_instances.qiao_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.qiao_id IS 'External persona identifier (multiple users can add same persona)';


--
-- Name: COLUMN ai_instances.creation_metadata; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.creation_metadata IS 'Immutable snapshot at creation time (persona_id, persona_qiao_id, persona_type_id, persona_type_name, template_id, template_display_name, etc.)';


--
-- Name: COLUMN ai_instances.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.status IS '1=active, 2=inactive, 3=blocking (AI has blocked the user)';


--
-- Name: COLUMN ai_instances.request_params; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.request_params IS 'AI instance request parameters configuration (JSON)';


--
-- Name: COLUMN ai_instances.llm_config_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.llm_config_id IS 'Preferred llm_configs.id; NULL falls back to primary config';


--
-- Name: COLUMN ai_instances.timezone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_instances.timezone IS 'IANA timezone for the instance (e.g., Asia/Shanghai)';


--
-- Name: ai_message_buffer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_message_buffer (
    id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    instance_qiao_id character varying(32) NOT NULL,
    aggregate_state smallint NOT NULL,
    micro_expires_at_ms bigint,
    macro_expires_at_ms bigint,
    buffer_expires_at_ms bigint,
    last_message_category character varying(32),
    first_msg_id_client character varying(64),
    last_msg_id_client character varying(64),
    message_count integer DEFAULT 1 NOT NULL,
    last_msg_time_ms bigint,
    locked_at timestamp with time zone,
    wake_adjustment_count smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    wake_delay_ms integer,
    CONSTRAINT ck_wake_delay_state CHECK ((((aggregate_state = 0) AND (wake_delay_ms IS NOT NULL)) OR ((aggregate_state <> 0) AND (wake_delay_ms IS NULL))))
);


--
-- Name: COLUMN ai_message_buffer.wake_adjustment_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_message_buffer.wake_adjustment_count IS 'Number of times wake time was adjusted by new messages';


--
-- Name: COLUMN ai_message_buffer.wake_delay_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_message_buffer.wake_delay_ms IS 'Wake delay (ms) applied after timer_due_ms; NULL when wake gate is inactive';


--
-- Name: ai_personalities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_personalities (
    id integer NOT NULL,
    display_name character varying(100) NOT NULL,
    prompt text NOT NULL,
    json_schema jsonb,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_personalities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_personalities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_personalities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_personalities_id_seq OWNED BY public.ai_personalities.id;


--
-- Name: ai_personality_placeholders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_personality_placeholders (
    id integer NOT NULL,
    personality_id integer NOT NULL,
    placeholder_key character varying(100) NOT NULL,
    display_name character varying(100) NOT NULL,
    description character varying(500),
    example_value text,
    is_required integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_personality_placeholders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_personality_placeholders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_personality_placeholders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_personality_placeholders_id_seq OWNED BY public.ai_personality_placeholders.id;


--
-- Name: ai_personas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_personas (
    id bigint NOT NULL,
    qiao_id character varying(32) NOT NULL,
    username character varying(20),
    type_id integer NOT NULL,
    is_reusable integer DEFAULT 1 NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tags jsonb,
    remark text
);


--
-- Name: TABLE ai_personas; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_personas IS 'AI personas - manages unique qiao_id inventory (similar to product SKU)';


--
-- Name: COLUMN ai_personas.qiao_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.qiao_id IS 'External unique identifier, visible to users in Square';


--
-- Name: COLUMN ai_personas.username; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.username IS 'Public AI username, unique in ai_personas (case-insensitive)';


--
-- Name: COLUMN ai_personas.type_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.type_id IS 'AI type ID (internal management), NOT related to Square categories';


--
-- Name: COLUMN ai_personas.is_reusable; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.is_reusable IS '1=reusable (multiple users can add), 0=non-reusable (only one user can add)';


--
-- Name: COLUMN ai_personas.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.status IS '1=active (visible), 2=inactive (hidden), 3=used (single-use consumed)';


--
-- Name: COLUMN ai_personas.tags; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.tags IS 'Preset contact tags written into contacts.tags on add';


--
-- Name: COLUMN ai_personas.remark; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_personas.remark IS 'Preset contact remark written into contacts.remark on add';


--
-- Name: ai_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_relationships (
    id integer NOT NULL,
    display_name character varying(100) NOT NULL,
    prompt_fragment text,
    status integer DEFAULT 1 NOT NULL,
    wake_time_min_ms integer DEFAULT 3000 NOT NULL,
    wake_time_max_ms integer DEFAULT 3000 NOT NULL,
    wake_time_bias character varying(20) DEFAULT 'balanced'::character varying NOT NULL,
    wake_window_ms integer DEFAULT 60000 NOT NULL,
    wake_time_adjustment character varying(20) DEFAULT 'random_half'::character varying NOT NULL,
    no_reply_probability numeric(3,2) DEFAULT 0.00 NOT NULL,
    followup_delay_ms integer DEFAULT 5000 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ai_relationships_check CHECK ((wake_time_max_ms >= wake_time_min_ms)),
    CONSTRAINT ai_relationships_followup_delay_ms_check CHECK ((followup_delay_ms >= 0)),
    CONSTRAINT ai_relationships_no_reply_probability_check CHECK (((no_reply_probability >= (0)::numeric) AND (no_reply_probability <= (1)::numeric))),
    CONSTRAINT ai_relationships_wake_time_adjustment_check CHECK (((wake_time_adjustment)::text <> ''::text)),
    CONSTRAINT ai_relationships_wake_time_bias_check CHECK (((wake_time_bias)::text <> ''::text)),
    CONSTRAINT ai_relationships_wake_time_min_ms_check CHECK ((wake_time_min_ms >= 500)),
    CONSTRAINT ai_relationships_wake_window_ms_check CHECK ((wake_window_ms >= 0))
);


--
-- Name: COLUMN ai_relationships.wake_time_min_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.wake_time_min_ms IS 'Minimum wake wait time (ms), minimum 500ms';


--
-- Name: COLUMN ai_relationships.wake_time_max_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.wake_time_max_ms IS 'Maximum wake wait time (ms), must be >= min';


--
-- Name: COLUMN ai_relationships.wake_time_bias; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.wake_time_bias IS 'Sampling bias: balanced/centered/fast/slow/very_fast/very_slow';


--
-- Name: COLUMN ai_relationships.wake_window_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.wake_window_ms IS 'Skip wake if last message within this window (ms)';


--
-- Name: COLUMN ai_relationships.wake_time_adjustment; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.wake_time_adjustment IS 'Wait time adjustment when new message arrives';


--
-- Name: COLUMN ai_relationships.no_reply_probability; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.no_reply_probability IS 'Probability of not replying after wake (0.00-1.00)';


--
-- Name: COLUMN ai_relationships.followup_delay_ms; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_relationships.followup_delay_ms IS 'Delay between outgoing and follow-up messages in milliseconds';


--
-- Name: ai_relationships_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_relationships_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_relationships_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_relationships_id_seq OWNED BY public.ai_relationships.id;


--
-- Name: ai_request_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_request_logs (
    id bigint NOT NULL,
    instance_id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    style_id integer NOT NULL,
    personality_id integer NOT NULL,
    request_type character varying(20) DEFAULT 'production'::character varying NOT NULL,
    provider_name character varying(50),
    model_name character varying(100),
    llm_config_id integer,
    response_id character varying(64),
    cache_hit boolean DEFAULT false NOT NULL,
    buffer_id bigint,
    request jsonb NOT NULL,
    response jsonb,
    status integer NOT NULL,
    token_count integer,
    response_time integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone
);


--
-- Name: ai_style_dimensions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_style_dimensions (
    id integer NOT NULL,
    style_id integer NOT NULL,
    dimension_id integer NOT NULL,
    initial_position integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ai_style_dimensions_initial_position_check CHECK (((initial_position >= 0) AND (initial_position <= 1000)))
);


--
-- Name: ai_style_dimensions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_style_dimensions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_style_dimensions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_style_dimensions_id_seq OWNED BY public.ai_style_dimensions.id;


--
-- Name: ai_styles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_styles (
    id integer NOT NULL,
    display_name character varying(100) NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: ai_styles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_styles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_styles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_styles_id_seq OWNED BY public.ai_styles.id;


--
-- Name: ai_template_memories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_template_memories (
    id bigint NOT NULL,
    template_id integer NOT NULL,
    memory_type character varying(20) NOT NULL,
    content text NOT NULL,
    importance integer DEFAULT 5 NOT NULL,
    display_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_template_memories_importance CHECK (((importance >= 1) AND (importance <= 10))),
    CONSTRAINT ck_template_memories_type CHECK (((memory_type)::text = ANY (ARRAY[('core'::character varying)::text, ('recent'::character varying)::text])))
);


--
-- Name: TABLE ai_template_memories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_template_memories IS 'Template seed memories - static memory definitions copied to instances during instantiation';


--
-- Name: COLUMN ai_template_memories.template_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_template_memories.template_id IS 'Reference to ai_templates.id';


--
-- Name: COLUMN ai_template_memories.memory_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_template_memories.memory_type IS 'core=permanent, recent=will fade with time';


--
-- Name: COLUMN ai_template_memories.content; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_template_memories.content IS 'Memory content - concise description';


--
-- Name: COLUMN ai_template_memories.importance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_template_memories.importance IS 'Importance level 1-10, determines lifetime (importance 脳 10 = days)';


--
-- Name: COLUMN ai_template_memories.display_order; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_template_memories.display_order IS 'Display and copy order, lower value = higher priority';


--
-- Name: ai_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_templates (
    id integer NOT NULL,
    type_id integer NOT NULL,
    style_id integer NOT NULL,
    personality_id integer NOT NULL,
    prompt_variables jsonb,
    request_params jsonb,
    llm_config_id integer,
    timezone character varying(50) DEFAULT 'Asia/Shanghai'::character varying NOT NULL,
    typing_speed_wpm integer NOT NULL,
    display_name character varying(100),
    position_mapping_config jsonb,
    is_reusable integer DEFAULT 1 NOT NULL,
    priority integer DEFAULT 1 NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE ai_templates; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_templates IS 'AI templates - core configuration templates for AI instances';


--
-- Name: COLUMN ai_templates.type_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.type_id IS 'AI type ID (internal management), NOT related to Square categories';


--
-- Name: COLUMN ai_templates.request_params; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.request_params IS 'Template-level LLM request parameters (temperature, max_tokens, etc.) - inherited by instances';


--
-- Name: COLUMN ai_templates.llm_config_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.llm_config_id IS 'Soft reference to llm_configs.id; NULL uses system default';


--
-- Name: COLUMN ai_templates.timezone; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.timezone IS 'Default IANA timezone copied to AI instances';


--
-- Name: COLUMN ai_templates.is_reusable; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.is_reusable IS '1=reusable (can create multiple instances), 0=non-reusable (can only create once)';


--
-- Name: COLUMN ai_templates.priority; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.priority IS 'Priority for selection, lower number = higher priority (non-reusable templates have priority)';


--
-- Name: COLUMN ai_templates.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_templates.status IS '1=active, 2=inactive, 3=used (only for is_reusable=0, after being used once)';


--
-- Name: ai_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_templates_id_seq OWNED BY public.ai_templates.id;


--
-- Name: ai_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_types (
    id integer NOT NULL,
    display_name character varying(100) NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE ai_types; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ai_types IS 'AI template types - INTERNAL inventory groupings, NOT related to Square categories';


--
-- Name: COLUMN ai_types.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ai_types.display_name IS 'Display name for admin dashboard';


--
-- Name: ai_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_types_id_seq OWNED BY public.ai_types.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: alert_event_entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert_event_entities (
    id bigint NOT NULL,
    event_id bigint NOT NULL,
    entity_type character varying(40) NOT NULL,
    entity_id character varying(128) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: alert_event_entities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alert_event_entities_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alert_event_entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alert_event_entities_id_seq OWNED BY public.alert_event_entities.id;


--
-- Name: alert_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alert_events (
    id bigint NOT NULL,
    event_type character varying(120) NOT NULL,
    domain character varying(40) NOT NULL,
    severity_level smallint NOT NULL,
    dedupe_key character varying(255),
    details jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_alert_events_severity_level CHECK ((severity_level = ANY (ARRAY[10, 20, 30, 40, 50])))
);


--
-- Name: alert_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.alert_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alert_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.alert_events_id_seq OWNED BY public.alert_events.id;


--
-- Name: app_pages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_pages (
    id bigint NOT NULL,
    page_key character varying(64) NOT NULL,
    client_type character varying(32) NOT NULL,
    locale character varying(16) NOT NULL,
    page_category smallint NOT NULL,
    title character varying(200),
    source_type smallint NOT NULL,
    content_md text,
    content_html text,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_app_pages_client_type CHECK (((client_type)::text = 'mini-program'::text)),
    CONSTRAINT ck_app_pages_locale CHECK (((locale)::text = 'zh-CN'::text)),
    CONSTRAINT ck_app_pages_page_category CHECK ((page_category = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_app_pages_source_type CHECK ((source_type = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_app_pages_status CHECK ((status = ANY (ARRAY[1, 2])))
);


--
-- Name: backup_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.backup_jobs (
    id integer NOT NULL,
    status integer NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    duration_ms bigint,
    backup_file_name character varying(255),
    object_key text,
    bucket_name character varying(255),
    storage_region character varying(64),
    file_size bigint,
    sha256 character varying(64),
    etag character varying(128),
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_backup_jobs_status CHECK ((status = ANY (ARRAY[1, 2, 3])))
);


--
-- Name: backup_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.backup_jobs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: backup_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.backup_jobs_id_seq OWNED BY public.backup_jobs.id;


--
-- Name: contact_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact_requests (
    id bigint NOT NULL,
    from_qiao_id character varying(32) NOT NULL,
    from_type integer NOT NULL,
    from_id bigint NOT NULL,
    to_qiao_id character varying(32) NOT NULL,
    to_type integer NOT NULL,
    to_id bigint,
    message text,
    source integer NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    failure_code character varying(50),
    failure_detail jsonb,
    retry_count integer DEFAULT 0 NOT NULL,
    last_retry_at timestamp with time zone,
    expires_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    category_key character varying(64),
    alias character varying(100),
    tags jsonb
);


--
-- Name: contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contacts (
    id bigint NOT NULL,
    conversation_id character varying(32) NOT NULL,
    user_id bigint,
    user_qiao_id character varying(32),
    contact_type integer NOT NULL,
    contact_id bigint NOT NULL,
    contact_qiao_id character varying(32) NOT NULL,
    alias character varying(100),
    custom_avatar_key character varying(255),
    custom_avatar_media_id bigint,
    tags jsonb,
    remark text,
    source integer DEFAULT 0 NOT NULL,
    is_pinned integer DEFAULT 0 NOT NULL,
    is_muted integer DEFAULT 0 NOT NULL,
    is_blocked integer DEFAULT 0 NOT NULL,
    is_deleted integer DEFAULT 0 NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    avatar_display_mode integer DEFAULT 1 NOT NULL,
    CONSTRAINT ck_contacts_avatar_display_mode CHECK ((avatar_display_mode = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_contacts_source CHECK ((source = ANY (ARRAY[0, 1, 2, 3, 4, 5, 6])))
);


--
-- Name: COLUMN contacts.avatar_display_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.contacts.avatar_display_mode IS 'Avatar display mode: 1=original, 2=custom';


--
-- Name: llm_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_configs (
    id integer NOT NULL,
    provider_id integer NOT NULL,
    name character varying(50) NOT NULL,
    model_name character varying(100),
    temperature numeric(3,2),
    max_tokens integer,
    timeout_seconds integer,
    thinking_mode character varying(20) DEFAULT 'auto'::character varying NOT NULL,
    top_p numeric(3,2) DEFAULT 0.70 NOT NULL,
    frequency_penalty numeric(3,2) DEFAULT 0.00 NOT NULL,
    presence_penalty numeric(3,2) DEFAULT 0.00 NOT NULL,
    stop_sequences jsonb DEFAULT '[]'::jsonb NOT NULL,
    json_schema_mode character varying(20),
    default_tools jsonb DEFAULT '[]'::jsonb NOT NULL,
    default_tool_choice character varying(30) DEFAULT 'auto'::character varying NOT NULL,
    parallel_tool_calls boolean DEFAULT false NOT NULL,
    max_tool_calls smallint DEFAULT 1 NOT NULL,
    default_extra_headers jsonb DEFAULT '{}'::jsonb NOT NULL,
    default_extra_query jsonb DEFAULT '{}'::jsonb NOT NULL,
    enable_streaming boolean DEFAULT false NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    priority integer DEFAULT 1 NOT NULL,
    extra_params jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_llm_configs_default_tool_choice CHECK (((default_tool_choice)::text <> ''::text)),
    CONSTRAINT ck_llm_configs_frequency_penalty CHECK (((frequency_penalty >= ('-2'::integer)::numeric) AND (frequency_penalty <= (2)::numeric))),
    CONSTRAINT ck_llm_configs_max_tool_calls CHECK ((max_tool_calls >= 0)),
    CONSTRAINT ck_llm_configs_presence_penalty CHECK (((presence_penalty >= ('-2'::integer)::numeric) AND (presence_penalty <= (2)::numeric))),
    CONSTRAINT ck_llm_configs_thinking_mode CHECK (((thinking_mode)::text <> ''::text)),
    CONSTRAINT ck_llm_configs_top_p CHECK (((top_p >= (0)::numeric) AND (top_p <= (1)::numeric)))
);


--
-- Name: COLUMN llm_configs.thinking_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.thinking_mode IS 'Thinking mode: enabled=force on, disabled=force off, auto=let model decide';


--
-- Name: COLUMN llm_configs.top_p; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.top_p IS 'Nucleus sampling threshold [0, 1]. Controls diversity of output.';


--
-- Name: COLUMN llm_configs.frequency_penalty; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.frequency_penalty IS 'Frequency penalty [-2, 2]. Reduces repetition based on token frequency.';


--
-- Name: COLUMN llm_configs.presence_penalty; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.presence_penalty IS 'Presence penalty [-2, 2]. Encourages new topics based on token presence.';


--
-- Name: COLUMN llm_configs.stop_sequences; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.stop_sequences IS 'Stop sequences (max 4 strings). Model stops when encountering these strings.';


--
-- Name: COLUMN llm_configs.json_schema_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.json_schema_mode IS 'JSON Schema support status: strict=verified supported, disabled=verified not supported, auto=not verified (default)';


--
-- Name: COLUMN llm_configs.default_tools; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.default_tools IS 'Default tool definitions in JSON array form';


--
-- Name: COLUMN llm_configs.default_tool_choice; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.default_tool_choice IS 'Tool choice behavior: auto/none/required';


--
-- Name: COLUMN llm_configs.parallel_tool_calls; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.parallel_tool_calls IS 'Allow provider to execute tools in parallel';


--
-- Name: COLUMN llm_configs.max_tool_calls; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.max_tool_calls IS 'Maximum number of tool calls allowed per request';


--
-- Name: COLUMN llm_configs.default_extra_headers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.default_extra_headers IS 'Default extra headers appended to each provider request';


--
-- Name: COLUMN llm_configs.default_extra_query; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.default_extra_query IS 'Default extra query parameters for each request';


--
-- Name: COLUMN llm_configs.enable_streaming; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_configs.enable_streaming IS 'Enable streaming output (experimental, default: false)';


--
-- Name: llm_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_configs_id_seq OWNED BY public.llm_configs.id;


--
-- Name: llm_providers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_providers (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    display_name character varying(100) NOT NULL,
    api_key_env character varying(100),
    base_url character varying(500),
    default_model character varying(100),
    supports_streaming integer NOT NULL,
    supports_json_schema integer NOT NULL,
    supports_thinking integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN llm_providers.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_providers.name IS 'Provider identifier (doubao, openai, claude, etc.)';


--
-- Name: COLUMN llm_providers.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_providers.display_name IS 'Display name for UI (must be unique)';


--
-- Name: COLUMN llm_providers.api_key_env; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_providers.api_key_env IS 'Environment variable name for API key (optional, defaults to {NAME}_API_KEY)';


--
-- Name: llm_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.llm_providers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: llm_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.llm_providers_id_seq OWNED BY public.llm_providers.id;


--
-- Name: llm_test_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.llm_test_logs (
    id bigint NOT NULL,
    config_id integer NOT NULL,
    config_name character varying(100) NOT NULL,
    provider_name character varying(50) NOT NULL,
    model_name character varying(100),
    test_message text NOT NULL,
    override_temperature numeric(3,2),
    override_max_tokens integer,
    thinking_mode character varying(20) NOT NULL,
    enable_json_schema integer NOT NULL,
    request jsonb NOT NULL,
    response jsonb,
    status integer NOT NULL,
    error_message text,
    response_time_ms integer,
    prompt_tokens integer,
    completion_tokens integer,
    total_tokens integer,
    reasoning_content text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT ck_llm_test_logs_thinking_mode CHECK (((thinking_mode)::text <> ''::text))
);


--
-- Name: COLUMN llm_test_logs.thinking_mode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.llm_test_logs.thinking_mode IS 'Thinking mode: enabled/disabled/auto';


--
-- Name: login_records; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.login_records (
    id bigint NOT NULL,
    user_id bigint,
    user_qiao_id character varying(32),
    login_time timestamp with time zone DEFAULT now() NOT NULL,
    login_type integer NOT NULL,
    platform integer NOT NULL,
    device_id uuid,
    ip_address inet,
    user_agent text,
    result integer NOT NULL,
    fail_reason character varying(255),
    user_token_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: media_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.media_files (
    id bigint NOT NULL,
    file_id character varying(32) NOT NULL,
    file_type smallint NOT NULL,
    category character varying(50),
    storage_provider character varying(20) NOT NULL,
    bucket_name character varying(100),
    object_key character varying(500) NOT NULL,
    storage_region character varying(50),
    original_name character varying(255) NOT NULL,
    file_size integer NOT NULL,
    mime_type character varying(100) NOT NULL,
    file_hash character varying(64),
    is_public boolean DEFAULT false,
    upload_by_type smallint NOT NULL,
    upload_by_id bigint,
    upload_by_qiao_id character varying(32),
    etag character varying(64),
    confirmed_at timestamp with time zone,
    confirmed_by_id bigint,
    status smallint DEFAULT 2 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT media_files_storage_provider_check CHECK (((storage_provider)::text = 'tencent_cos'::text))
);


--
-- Name: COLUMN media_files.etag; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.media_files.etag IS 'ETag returned by storage provider (for upload verification)';


--
-- Name: COLUMN media_files.confirmed_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.media_files.confirmed_at IS 'Upload confirmation timestamp';


--
-- Name: COLUMN media_files.confirmed_by_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.media_files.confirmed_by_id IS 'User/admin ID who confirmed the upload (for audit trail)';


--
-- Name: COLUMN media_files.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.media_files.status IS 'File status: 1=active, 2=pending (awaiting confirmation), 3=deleted (soft delete)';


--
-- Name: message_deliveries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_deliveries (
    id bigint NOT NULL,
    msg_id_server character varying(64) NOT NULL,
    endpoint_id bigint NOT NULL,
    provider smallint NOT NULL,
    target_key character varying(256) NOT NULL,
    provider_msg_id character varying(128),
    status smallint NOT NULL,
    dispatched_at timestamp with time zone,
    failed_reason_code character varying(50),
    failed_detail text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_message_deliveries_provider CHECK ((provider = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_message_deliveries_status CHECK ((status = ANY (ARRAY[1, 2, 3])))
);


--
-- Name: message_devices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_devices (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    device_id uuid NOT NULL,
    last_acked_msg_id character varying(64),
    last_acked_msg_sent_at timestamp with time zone,
    last_pull_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: message_dispatch_outbox; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_dispatch_outbox (
    id bigint NOT NULL,
    outbox_type smallint NOT NULL,
    msg_id_server character varying(64) NOT NULL,
    owner_user_id bigint NOT NULL,
    status smallint NOT NULL,
    attempt_count integer DEFAULT 0 NOT NULL,
    next_retry_at timestamp with time zone,
    locked_at timestamp with time zone,
    last_error_code character varying(50),
    last_error_detail text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_message_dispatch_outbox_attempt_count CHECK ((attempt_count >= 0)),
    CONSTRAINT ck_message_dispatch_outbox_status CHECK ((status = ANY (ARRAY[1, 2, 3, 4]))),
    CONSTRAINT ck_message_dispatch_outbox_type CHECK ((outbox_type = 1))
);


--
-- Name: message_endpoints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_endpoints (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    endpoint_scope smallint NOT NULL,
    device_id uuid,
    provider smallint NOT NULL,
    target_key character varying(256) NOT NULL,
    client_kind smallint,
    lease_expires_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_message_endpoints_provider CHECK ((provider = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_message_endpoints_scope CHECK ((endpoint_scope = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_message_endpoints_scope_device CHECK ((((endpoint_scope = 1) AND (device_id IS NULL)) OR ((endpoint_scope = 2) AND (device_id IS NOT NULL))))
);


--
-- Name: message_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_history (
    id bigint NOT NULL,
    direction integer NOT NULL,
    conversation_id character varying(32) NOT NULL,
    msg_id_server character varying(64) NOT NULL,
    msg_id_provider_inbound character varying(128),
    msg_id_client character varying(64),
    client_sent_at timestamp with time zone,
    sent_at timestamp with time zone,
    from_type integer NOT NULL,
    from_id bigint NOT NULL,
    from_qiao_id character varying(32) NOT NULL,
    to_type integer NOT NULL,
    to_id bigint NOT NULL,
    to_qiao_id character varying(32) NOT NULL,
    message_type integer NOT NULL,
    content text,
    inbound_provider smallint,
    inbound_device_id uuid,
    message_metadata jsonb,
    llm_request_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_message_history_inbound_provider CHECK (((inbound_provider IS NULL) OR (inbound_provider = ANY (ARRAY[1, 2]))))
);


--
-- Name: notification_push_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_push_history (
    id bigint NOT NULL,
    to_qiao_id character varying(32) NOT NULL,
    notification_type integer NOT NULL,
    action_data jsonb NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profiles (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    owner_qiao_id character varying(32) NOT NULL,
    owner_type integer NOT NULL,
    nickname character varying(100),
    gender integer,
    avatar_key character varying(255),
    avatar_media_id bigint,
    avatar_prompt text,
    bio text,
    region character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    region_country_code character varying(2),
    region_cn_city_code character varying(6)
);


--
-- Name: COLUMN profiles.region_country_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.profiles.region_country_code IS 'Region country/territory code (ISO 3166-1 alpha-2, e.g. CN/HK/MO/TW)';


--
-- Name: COLUMN profiles.region_cn_city_code; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.profiles.region_cn_city_code IS 'CN city-level administrative division code (6 digits), only when region_country_code=CN';


--
-- Name: square_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_categories (
    id bigint NOT NULL,
    category_key character varying(64) NOT NULL,
    title character varying(50) NOT NULL,
    description text,
    theme_key character varying(20) NOT NULL,
    icon_ref character varying(100) NOT NULL,
    sort_order integer DEFAULT 100 NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_square_categories_category_key_format CHECK (((category_key)::text ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'::text)),
    CONSTRAINT ck_square_categories_icon_ref_format CHECK (((icon_ref)::text ~ '^tdesign:[a-z0-9-]+$'::text)),
    CONSTRAINT ck_square_categories_status CHECK ((status = ANY (ARRAY[1, 2]))),
    CONSTRAINT ck_square_categories_theme_key CHECK (((theme_key)::text = ANY ((ARRAY['blue'::character varying, 'cyan'::character varying, 'teal'::character varying, 'green'::character varying, 'lime'::character varying, 'yellow'::character varying, 'orange'::character varying, 'purple'::character varying, 'pink'::character varying, 'magenta'::character varying, 'beige'::character varying, 'charcoal'::character varying])::text[]))),
    CONSTRAINT ck_square_categories_title_length CHECK ((char_length((title)::text) <= 20))
);


--
-- Name: TABLE square_categories; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.square_categories IS 'Square category definitions for dynamic discovery tabs';


--
-- Name: square_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_categories_id_seq OWNED BY public.square_categories.id;


--
-- Name: square_type_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.square_type_entries (
    id integer NOT NULL,
    type_id integer NOT NULL,
    exposure_strategy integer DEFAULT 1 NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    category_key character varying(64) NOT NULL,
    CONSTRAINT ck_square_type_entries_status CHECK ((status = ANY (ARRAY[1, 2])))
);


--
-- Name: TABLE square_type_entries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.square_type_entries IS 'Square discovery entries - decoupled from template/profile inventory';


--
-- Name: COLUMN square_type_entries.type_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_type_entries.type_id IS 'AI type exposed in this slot (references ai_types)';


--
-- Name: COLUMN square_type_entries.exposure_strategy; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_type_entries.exposure_strategy IS 'Exposure strategy enum: 1=random';


--
-- Name: COLUMN square_type_entries.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.square_type_entries.status IS '1=active, 2=inactive';


--
-- Name: square_type_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.square_type_entries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: square_type_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.square_type_entries_id_seq OWNED BY public.square_type_entries.id;


--
-- Name: stats_ai_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_ai_daily (
    id integer NOT NULL,
    stat_date date NOT NULL,
    ai_instances integer DEFAULT 0 NOT NULL,
    active_ai_instances integer DEFAULT 0 NOT NULL,
    ai_requests_count integer DEFAULT 0 NOT NULL,
    avg_ai_requests_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_ai_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_ai_daily_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_ai_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_ai_daily_id_seq OWNED BY public.stats_ai_daily.id;


--
-- Name: stats_ai_monthly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_ai_monthly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    ai_instances integer DEFAULT 0 NOT NULL,
    active_ai_instances integer DEFAULT 0 NOT NULL,
    ai_requests_count integer DEFAULT 0 NOT NULL,
    avg_ai_requests_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_ai_monthly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_ai_monthly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_ai_monthly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_ai_monthly_id_seq OWNED BY public.stats_ai_monthly.id;


--
-- Name: stats_ai_weekly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_ai_weekly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    ai_instances integer DEFAULT 0 NOT NULL,
    active_ai_instances integer DEFAULT 0 NOT NULL,
    ai_requests_count integer DEFAULT 0 NOT NULL,
    avg_ai_requests_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_ai_weekly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_ai_weekly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_ai_weekly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_ai_weekly_id_seq OWNED BY public.stats_ai_weekly.id;


--
-- Name: stats_message_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_message_daily (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_messages integer DEFAULT 0 NOT NULL,
    avg_messages_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    active_conversations integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_message_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_message_daily_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_message_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_message_daily_id_seq OWNED BY public.stats_message_daily.id;


--
-- Name: stats_message_monthly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_message_monthly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_messages integer DEFAULT 0 NOT NULL,
    avg_messages_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    active_conversations integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_message_monthly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_message_monthly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_message_monthly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_message_monthly_id_seq OWNED BY public.stats_message_monthly.id;


--
-- Name: stats_message_weekly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_message_weekly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_messages integer DEFAULT 0 NOT NULL,
    avg_messages_per_user numeric(10,2) DEFAULT 0 NOT NULL,
    active_conversations integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_message_weekly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_message_weekly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_message_weekly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_message_weekly_id_seq OWNED BY public.stats_message_weekly.id;


--
-- Name: stats_user_daily; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_user_daily (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_users integer DEFAULT 0 NOT NULL,
    new_users integer DEFAULT 0 NOT NULL,
    active_users integer DEFAULT 0 NOT NULL,
    subscriptions integer DEFAULT 0 NOT NULL,
    new_subscriptions integer DEFAULT 0 NOT NULL,
    canceled_subscriptions integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_user_daily_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_user_daily_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_user_daily_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_user_daily_id_seq OWNED BY public.stats_user_daily.id;


--
-- Name: stats_user_monthly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_user_monthly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_users integer DEFAULT 0 NOT NULL,
    new_users integer DEFAULT 0 NOT NULL,
    active_users integer DEFAULT 0 NOT NULL,
    subscriptions integer DEFAULT 0 NOT NULL,
    new_subscriptions integer DEFAULT 0 NOT NULL,
    canceled_subscriptions integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_user_monthly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_user_monthly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_user_monthly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_user_monthly_id_seq OWNED BY public.stats_user_monthly.id;


--
-- Name: stats_user_weekly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stats_user_weekly (
    id integer NOT NULL,
    stat_date date NOT NULL,
    total_users integer DEFAULT 0 NOT NULL,
    new_users integer DEFAULT 0 NOT NULL,
    active_users integer DEFAULT 0 NOT NULL,
    subscriptions integer DEFAULT 0 NOT NULL,
    new_subscriptions integer DEFAULT 0 NOT NULL,
    canceled_subscriptions integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stats_user_weekly_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stats_user_weekly_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: stats_user_weekly_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stats_user_weekly_id_seq OWNED BY public.stats_user_weekly.id;


--
-- Name: system_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_configs (
    id integer NOT NULL,
    config_key character varying(100) NOT NULL,
    config_value text NOT NULL,
    default_value text NOT NULL,
    config_type integer NOT NULL,
    description text,
    updated_by integer,
    group_name character varying(50),
    allowed_values jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: system_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.system_configs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: system_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.system_configs_id_seq OWNED BY public.system_configs.id;


--
-- Name: user_auths; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_auths (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    auth_type integer NOT NULL,
    provider_uid character varying(128) NOT NULL,
    unionid character varying(64),
    app_id character varying(64),
    extra_data jsonb,
    status integer DEFAULT 1 NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_profile_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_profile_logs (
    id bigint NOT NULL,
    owner_id bigint NOT NULL,
    owner_qiao_id character varying(32) NOT NULL,
    owner_type integer NOT NULL,
    modified_by_type integer NOT NULL,
    field_name character varying(50) NOT NULL,
    old_value text,
    new_value text,
    change_reason character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_risk_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_risk_stats (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    total_violations integer DEFAULT 0 NOT NULL,
    violation_by_type jsonb DEFAULT '{}'::jsonb NOT NULL,
    last_violation_at timestamp with time zone,
    current_risk_level integer DEFAULT 1 NOT NULL,
    consecutive_violations integer DEFAULT 0 NOT NULL,
    warning_count integer DEFAULT 0 NOT NULL,
    restriction_count integer DEFAULT 0 NOT NULL,
    suspension_count integer DEFAULT 0 NOT NULL,
    last_action_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_tokens (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    access_token character varying(512) NOT NULL,
    device_type integer NOT NULL,
    device_id uuid NOT NULL,
    platform_info jsonb,
    ip_address inet,
    user_agent text,
    access_expires_at timestamp with time zone NOT NULL,
    status integer DEFAULT 1 NOT NULL,
    last_activity_at timestamp with time zone,
    access_revoked_at timestamp with time zone,
    refresh_token_hash character varying(512),
    refresh_expires_at timestamp with time zone,
    refresh_revoked_at timestamp with time zone,
    token_metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: user_violation_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_violation_logs (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_qiao_id character varying(32) NOT NULL,
    instance_id bigint,
    instance_qiao_id character varying(32),
    violation_type integer NOT NULL,
    severity_level integer NOT NULL,
    original_message text NOT NULL,
    auto_action_taken integer DEFAULT 1 NOT NULL,
    manual_review_status integer DEFAULT 1 NOT NULL,
    reviewer_id integer,
    review_notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    qiao_id character varying(32) NOT NULL,
    username character varying(20),
    phone character varying(20),
    email character varying(100),
    password_hash character varying(255),
    is_verified integer DEFAULT 0 NOT NULL,
    verified_at timestamp with time zone,
    verify_source character varying(100),
    verification_info jsonb,
    status integer DEFAULT 1 NOT NULL,
    needs_profile_setup boolean DEFAULT true NOT NULL,
    user_type integer DEFAULT 1 NOT NULL,
    last_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    minor_mode_enabled boolean DEFAULT false NOT NULL,
    minor_mode_pin_hash character varying(255),
    minor_mode_enabled_at timestamp with time zone,
    minor_mode_disabled_at timestamp with time zone,
    minor_mode_pin_updated_at timestamp with time zone,
    CONSTRAINT ck_users_username_length CHECK (((username IS NULL) OR ((char_length((username)::text) >= 5) AND (char_length((username)::text) <= 20))))
);


--
-- Name: COLUMN users.minor_mode_enabled; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.minor_mode_enabled IS 'Whether minor mode is enabled';


--
-- Name: COLUMN users.minor_mode_pin_hash; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.minor_mode_pin_hash IS 'Minor mode PIN hash';


--
-- Name: COLUMN users.minor_mode_enabled_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.minor_mode_enabled_at IS 'Minor mode enable timestamp';


--
-- Name: COLUMN users.minor_mode_disabled_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.minor_mode_disabled_at IS 'Minor mode disable timestamp';


--
-- Name: COLUMN users.minor_mode_pin_updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.users.minor_mode_pin_updated_at IS 'Minor mode PIN last update timestamp';


--
-- Name: admin_login_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_login_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_login_logs_id_seq'::regclass);


--
-- Name: admin_operation_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_operation_logs ALTER COLUMN id SET DEFAULT nextval('public.admin_operation_logs_id_seq'::regclass);


--
-- Name: admin_users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users ALTER COLUMN id SET DEFAULT nextval('public.admin_users_id_seq'::regclass);


--
-- Name: ai_buffer_wake_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_buffer_wake_events ALTER COLUMN id SET DEFAULT nextval('public.ai_buffer_wake_events_id_seq'::regclass);


--
-- Name: ai_dimension_relationship_mappings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimension_relationship_mappings ALTER COLUMN id SET DEFAULT nextval('public.ai_dimension_relationship_mappings_id_seq'::regclass);


--
-- Name: ai_dimensions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimensions ALTER COLUMN id SET DEFAULT nextval('public.ai_dimensions_id_seq'::regclass);


--
-- Name: ai_personalities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personalities ALTER COLUMN id SET DEFAULT nextval('public.ai_personalities_id_seq'::regclass);


--
-- Name: ai_personality_placeholders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personality_placeholders ALTER COLUMN id SET DEFAULT nextval('public.ai_personality_placeholders_id_seq'::regclass);


--
-- Name: ai_relationships id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_relationships ALTER COLUMN id SET DEFAULT nextval('public.ai_relationships_id_seq'::regclass);


--
-- Name: ai_style_dimensions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_style_dimensions ALTER COLUMN id SET DEFAULT nextval('public.ai_style_dimensions_id_seq'::regclass);


--
-- Name: ai_styles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_styles ALTER COLUMN id SET DEFAULT nextval('public.ai_styles_id_seq'::regclass);


--
-- Name: ai_templates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_templates ALTER COLUMN id SET DEFAULT nextval('public.ai_templates_id_seq'::regclass);


--
-- Name: ai_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_types ALTER COLUMN id SET DEFAULT nextval('public.ai_types_id_seq'::regclass);


--
-- Name: alert_event_entities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_event_entities ALTER COLUMN id SET DEFAULT nextval('public.alert_event_entities_id_seq'::regclass);


--
-- Name: alert_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_events ALTER COLUMN id SET DEFAULT nextval('public.alert_events_id_seq'::regclass);


--
-- Name: backup_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backup_jobs ALTER COLUMN id SET DEFAULT nextval('public.backup_jobs_id_seq'::regclass);


--
-- Name: llm_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_configs ALTER COLUMN id SET DEFAULT nextval('public.llm_configs_id_seq'::regclass);


--
-- Name: llm_providers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_providers ALTER COLUMN id SET DEFAULT nextval('public.llm_providers_id_seq'::regclass);


--
-- Name: square_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_categories ALTER COLUMN id SET DEFAULT nextval('public.square_categories_id_seq'::regclass);


--
-- Name: square_type_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_type_entries ALTER COLUMN id SET DEFAULT nextval('public.square_type_entries_id_seq'::regclass);


--
-- Name: stats_ai_daily id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_daily ALTER COLUMN id SET DEFAULT nextval('public.stats_ai_daily_id_seq'::regclass);


--
-- Name: stats_ai_monthly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_monthly ALTER COLUMN id SET DEFAULT nextval('public.stats_ai_monthly_id_seq'::regclass);


--
-- Name: stats_ai_weekly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_weekly ALTER COLUMN id SET DEFAULT nextval('public.stats_ai_weekly_id_seq'::regclass);


--
-- Name: stats_message_daily id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_daily ALTER COLUMN id SET DEFAULT nextval('public.stats_message_daily_id_seq'::regclass);


--
-- Name: stats_message_monthly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_monthly ALTER COLUMN id SET DEFAULT nextval('public.stats_message_monthly_id_seq'::regclass);


--
-- Name: stats_message_weekly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_weekly ALTER COLUMN id SET DEFAULT nextval('public.stats_message_weekly_id_seq'::regclass);


--
-- Name: stats_user_daily id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_daily ALTER COLUMN id SET DEFAULT nextval('public.stats_user_daily_id_seq'::regclass);


--
-- Name: stats_user_monthly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_monthly ALTER COLUMN id SET DEFAULT nextval('public.stats_user_monthly_id_seq'::regclass);


--
-- Name: stats_user_weekly id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_weekly ALTER COLUMN id SET DEFAULT nextval('public.stats_user_weekly_id_seq'::regclass);


--
-- Name: system_configs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs ALTER COLUMN id SET DEFAULT nextval('public.system_configs_id_seq'::regclass);


--
-- Name: admin_login_logs admin_login_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_login_logs
    ADD CONSTRAINT admin_login_logs_pkey PRIMARY KEY (id);


--
-- Name: admin_operation_logs admin_operation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_operation_logs
    ADD CONSTRAINT admin_operation_logs_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_pkey PRIMARY KEY (id);


--
-- Name: admin_users admin_users_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admin_users
    ADD CONSTRAINT admin_users_username_key UNIQUE (username);


--
-- Name: ai_conversation_items_archive ai_conversation_items_archive_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversation_items_archive
    ADD CONSTRAINT ai_conversation_items_archive_pkey PRIMARY KEY (id);


--
-- Name: ai_conversation_items ai_conversation_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversation_items
    ADD CONSTRAINT ai_conversation_items_pkey PRIMARY KEY (id);


--
-- Name: ai_conversation_runtime ai_conversation_runtime_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversation_runtime
    ADD CONSTRAINT ai_conversation_runtime_pkey PRIMARY KEY (user_qiao_id, instance_qiao_id);


--
-- Name: ai_conversation_state ai_conversation_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_conversation_state
    ADD CONSTRAINT ai_conversation_state_pkey PRIMARY KEY (user_qiao_id, instance_qiao_id);


--
-- Name: ai_dimension_relationship_mappings ai_dimension_relationship_mappings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimension_relationship_mappings
    ADD CONSTRAINT ai_dimension_relationship_mappings_pkey PRIMARY KEY (id);


--
-- Name: ai_dimensions ai_dimensions_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimensions
    ADD CONSTRAINT ai_dimensions_name_key UNIQUE (name);


--
-- Name: ai_dimensions ai_dimensions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimensions
    ADD CONSTRAINT ai_dimensions_pkey PRIMARY KEY (id);


--
-- Name: ai_instance_dimensions ai_instance_dimensions_instance_id_dimension_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_dimensions
    ADD CONSTRAINT ai_instance_dimensions_instance_id_dimension_id_key UNIQUE (instance_id, dimension_id);


--
-- Name: ai_instance_dimensions ai_instance_dimensions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_dimensions
    ADD CONSTRAINT ai_instance_dimensions_pkey PRIMARY KEY (id);


--
-- Name: ai_instance_memories ai_instance_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_memories
    ADD CONSTRAINT ai_instance_memories_pkey PRIMARY KEY (id);


--
-- Name: ai_instances ai_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT ai_instances_pkey PRIMARY KEY (id);


--
-- Name: ai_message_buffer ai_message_buffer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_message_buffer
    ADD CONSTRAINT ai_message_buffer_pkey PRIMARY KEY (id);


--
-- Name: ai_personalities ai_personalities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personalities
    ADD CONSTRAINT ai_personalities_pkey PRIMARY KEY (id);


--
-- Name: ai_personality_placeholders ai_personality_placeholders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personality_placeholders
    ADD CONSTRAINT ai_personality_placeholders_pkey PRIMARY KEY (id);


--
-- Name: ai_personas ai_personas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personas
    ADD CONSTRAINT ai_personas_pkey PRIMARY KEY (id);


--
-- Name: ai_personas ai_personas_qiao_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personas
    ADD CONSTRAINT ai_personas_qiao_id_key UNIQUE (qiao_id);


--
-- Name: ai_relationships ai_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_relationships
    ADD CONSTRAINT ai_relationships_pkey PRIMARY KEY (id);


--
-- Name: ai_request_logs ai_request_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_request_logs
    ADD CONSTRAINT ai_request_logs_pkey PRIMARY KEY (id);


--
-- Name: ai_style_dimensions ai_style_dimensions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_style_dimensions
    ADD CONSTRAINT ai_style_dimensions_pkey PRIMARY KEY (id);


--
-- Name: ai_style_dimensions ai_style_dimensions_style_id_dimension_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_style_dimensions
    ADD CONSTRAINT ai_style_dimensions_style_id_dimension_id_key UNIQUE (style_id, dimension_id);


--
-- Name: ai_styles ai_styles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_styles
    ADD CONSTRAINT ai_styles_pkey PRIMARY KEY (id);


--
-- Name: ai_template_memories ai_template_memories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_template_memories
    ADD CONSTRAINT ai_template_memories_pkey PRIMARY KEY (id);


--
-- Name: ai_templates ai_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_templates
    ADD CONSTRAINT ai_templates_pkey PRIMARY KEY (id);


--
-- Name: ai_types ai_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_types
    ADD CONSTRAINT ai_types_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: alert_event_entities alert_event_entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_event_entities
    ADD CONSTRAINT alert_event_entities_pkey PRIMARY KEY (id);


--
-- Name: alert_events alert_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alert_events
    ADD CONSTRAINT alert_events_pkey PRIMARY KEY (id);


--
-- Name: app_pages app_pages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_pages
    ADD CONSTRAINT app_pages_pkey PRIMARY KEY (id);


--
-- Name: backup_jobs backup_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.backup_jobs
    ADD CONSTRAINT backup_jobs_pkey PRIMARY KEY (id);


--
-- Name: contact_requests contact_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_requests
    ADD CONSTRAINT contact_requests_pkey PRIMARY KEY (id);


--
-- Name: contacts contacts_conversation_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_conversation_id_key UNIQUE (conversation_id);


--
-- Name: contacts contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_pkey PRIMARY KEY (id);


--
-- Name: llm_configs llm_configs_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_configs
    ADD CONSTRAINT llm_configs_name_key UNIQUE (name);


--
-- Name: llm_configs llm_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_configs
    ADD CONSTRAINT llm_configs_pkey PRIMARY KEY (id);


--
-- Name: llm_providers llm_providers_display_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_providers
    ADD CONSTRAINT llm_providers_display_name_key UNIQUE (display_name);


--
-- Name: llm_providers llm_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_providers
    ADD CONSTRAINT llm_providers_pkey PRIMARY KEY (id);


--
-- Name: llm_test_logs llm_test_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_test_logs
    ADD CONSTRAINT llm_test_logs_pkey PRIMARY KEY (id);


--
-- Name: login_records login_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records
    ADD CONSTRAINT login_records_pkey PRIMARY KEY (id);


--
-- Name: media_files media_files_file_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_files
    ADD CONSTRAINT media_files_file_id_key UNIQUE (file_id);


--
-- Name: media_files media_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.media_files
    ADD CONSTRAINT media_files_pkey PRIMARY KEY (id);


--
-- Name: message_deliveries message_deliveries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_deliveries
    ADD CONSTRAINT message_deliveries_pkey PRIMARY KEY (id);


--
-- Name: message_devices message_devices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_devices
    ADD CONSTRAINT message_devices_pkey PRIMARY KEY (id);


--
-- Name: message_dispatch_outbox message_dispatch_outbox_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_dispatch_outbox
    ADD CONSTRAINT message_dispatch_outbox_pkey PRIMARY KEY (id);


--
-- Name: message_endpoints message_endpoints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_endpoints
    ADD CONSTRAINT message_endpoints_pkey PRIMARY KEY (id);


--
-- Name: message_history message_history_msg_id_server_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_history
    ADD CONSTRAINT message_history_msg_id_server_key UNIQUE (msg_id_server);


--
-- Name: message_history message_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_history
    ADD CONSTRAINT message_history_pkey PRIMARY KEY (id);


--
-- Name: notification_push_history notification_push_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_push_history
    ADD CONSTRAINT notification_push_history_pkey PRIMARY KEY (id);


--
-- Name: ai_buffer_wake_events pk_ai_buffer_wake_events; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_buffer_wake_events
    ADD CONSTRAINT pk_ai_buffer_wake_events PRIMARY KEY (id);


--
-- Name: profiles profiles_owner_qiao_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_owner_qiao_id_key UNIQUE (owner_qiao_id);


--
-- Name: profiles profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT profiles_pkey PRIMARY KEY (id);


--
-- Name: square_categories square_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_categories
    ADD CONSTRAINT square_categories_pkey PRIMARY KEY (id);


--
-- Name: square_type_entries square_type_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_type_entries
    ADD CONSTRAINT square_type_entries_pkey PRIMARY KEY (id);


--
-- Name: stats_ai_daily stats_ai_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_daily
    ADD CONSTRAINT stats_ai_daily_pkey PRIMARY KEY (id);


--
-- Name: stats_ai_daily stats_ai_daily_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_daily
    ADD CONSTRAINT stats_ai_daily_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_ai_monthly stats_ai_monthly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_monthly
    ADD CONSTRAINT stats_ai_monthly_pkey PRIMARY KEY (id);


--
-- Name: stats_ai_monthly stats_ai_monthly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_monthly
    ADD CONSTRAINT stats_ai_monthly_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_ai_weekly stats_ai_weekly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_weekly
    ADD CONSTRAINT stats_ai_weekly_pkey PRIMARY KEY (id);


--
-- Name: stats_ai_weekly stats_ai_weekly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_ai_weekly
    ADD CONSTRAINT stats_ai_weekly_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_message_daily stats_message_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_daily
    ADD CONSTRAINT stats_message_daily_pkey PRIMARY KEY (id);


--
-- Name: stats_message_daily stats_message_daily_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_daily
    ADD CONSTRAINT stats_message_daily_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_message_monthly stats_message_monthly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_monthly
    ADD CONSTRAINT stats_message_monthly_pkey PRIMARY KEY (id);


--
-- Name: stats_message_monthly stats_message_monthly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_monthly
    ADD CONSTRAINT stats_message_monthly_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_message_weekly stats_message_weekly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_weekly
    ADD CONSTRAINT stats_message_weekly_pkey PRIMARY KEY (id);


--
-- Name: stats_message_weekly stats_message_weekly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_message_weekly
    ADD CONSTRAINT stats_message_weekly_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_user_daily stats_user_daily_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_daily
    ADD CONSTRAINT stats_user_daily_pkey PRIMARY KEY (id);


--
-- Name: stats_user_daily stats_user_daily_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_daily
    ADD CONSTRAINT stats_user_daily_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_user_monthly stats_user_monthly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_monthly
    ADD CONSTRAINT stats_user_monthly_pkey PRIMARY KEY (id);


--
-- Name: stats_user_monthly stats_user_monthly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_monthly
    ADD CONSTRAINT stats_user_monthly_stat_date_key UNIQUE (stat_date);


--
-- Name: stats_user_weekly stats_user_weekly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_weekly
    ADD CONSTRAINT stats_user_weekly_pkey PRIMARY KEY (id);


--
-- Name: stats_user_weekly stats_user_weekly_stat_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stats_user_weekly
    ADD CONSTRAINT stats_user_weekly_stat_date_key UNIQUE (stat_date);


--
-- Name: system_configs system_configs_config_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs
    ADD CONSTRAINT system_configs_config_key_key UNIQUE (config_key);


--
-- Name: system_configs system_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_configs
    ADD CONSTRAINT system_configs_pkey PRIMARY KEY (id);


--
-- Name: ai_instances uq_ai_instances_user_qiao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT uq_ai_instances_user_qiao UNIQUE (user_id, qiao_id);


--
-- Name: app_pages uq_app_pages_page_client_locale; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_pages
    ADD CONSTRAINT uq_app_pages_page_client_locale UNIQUE (page_key, client_type, locale);


--
-- Name: contacts uq_contacts_user_contact_qiao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT uq_contacts_user_contact_qiao UNIQUE (user_id, contact_qiao_id);


--
-- Name: message_deliveries uq_message_deliveries_msg_endpoint; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_deliveries
    ADD CONSTRAINT uq_message_deliveries_msg_endpoint UNIQUE (msg_id_server, endpoint_id);


--
-- Name: message_devices uq_message_devices_user_device; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_devices
    ADD CONSTRAINT uq_message_devices_user_device UNIQUE (user_id, device_id);


--
-- Name: message_dispatch_outbox uq_message_dispatch_outbox_type_msg; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_dispatch_outbox
    ADD CONSTRAINT uq_message_dispatch_outbox_type_msg UNIQUE (outbox_type, msg_id_server);


--
-- Name: message_endpoints uq_message_endpoints_provider_user_target; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_endpoints
    ADD CONSTRAINT uq_message_endpoints_provider_user_target UNIQUE (provider, user_id, target_key);


--
-- Name: message_history uq_message_history_conv_client_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_history
    ADD CONSTRAINT uq_message_history_conv_client_id UNIQUE (conversation_id, msg_id_client);


--
-- Name: square_categories uq_square_categories_category_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_categories
    ADD CONSTRAINT uq_square_categories_category_key UNIQUE (category_key);


--
-- Name: square_type_entries uq_square_type_entries_category_key_type_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_type_entries
    ADD CONSTRAINT uq_square_type_entries_category_key_type_id UNIQUE (category_key, type_id);


--
-- Name: user_auths uq_user_auths_type_provider; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auths
    ADD CONSTRAINT uq_user_auths_type_provider UNIQUE (auth_type, provider_uid);


--
-- Name: user_auths user_auths_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auths
    ADD CONSTRAINT user_auths_pkey PRIMARY KEY (id);


--
-- Name: user_profile_logs user_profile_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_profile_logs
    ADD CONSTRAINT user_profile_logs_pkey PRIMARY KEY (id);


--
-- Name: user_risk_stats user_risk_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_risk_stats
    ADD CONSTRAINT user_risk_stats_pkey PRIMARY KEY (id);


--
-- Name: user_risk_stats user_risk_stats_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_risk_stats
    ADD CONSTRAINT user_risk_stats_user_id_key UNIQUE (user_id);


--
-- Name: user_risk_stats user_risk_stats_user_qiao_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_risk_stats
    ADD CONSTRAINT user_risk_stats_user_qiao_id_key UNIQUE (user_qiao_id);


--
-- Name: user_tokens user_tokens_access_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tokens
    ADD CONSTRAINT user_tokens_access_token_key UNIQUE (access_token);


--
-- Name: user_tokens user_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tokens
    ADD CONSTRAINT user_tokens_pkey PRIMARY KEY (id);


--
-- Name: user_violation_logs user_violation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_violation_logs
    ADD CONSTRAINT user_violation_logs_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_qiao_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_qiao_id_key UNIQUE (qiao_id);


--
-- Name: idx_ai_buffer_wake_events_buffer_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_buffer_wake_events_buffer_time ON public.ai_buffer_wake_events USING btree (buffer_id, created_at);


--
-- Name: idx_ai_conv_items_archive_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conv_items_archive_session ON public.ai_conversation_items_archive USING btree (user_qiao_id, instance_qiao_id, created_at DESC);


--
-- Name: idx_ai_conv_items_buffer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conv_items_buffer ON public.ai_conversation_items USING btree (buffer_id) WHERE (buffer_id IS NOT NULL);


--
-- Name: idx_ai_conv_items_excluded; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conv_items_excluded ON public.ai_conversation_items USING btree (user_qiao_id, instance_qiao_id, created_at DESC) WHERE (is_excluded_from_context = 1);


--
-- Name: idx_ai_conv_items_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conv_items_session ON public.ai_conversation_items USING btree (user_qiao_id, instance_qiao_id, created_at DESC);


--
-- Name: idx_ai_conv_items_text_search; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conv_items_text_search ON public.ai_conversation_items USING gin (text_content public.gin_trgm_ops);


--
-- Name: idx_ai_conversation_runtime_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversation_runtime_updated ON public.ai_conversation_runtime USING btree (updated_at);


--
-- Name: idx_ai_conversation_state_updated; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_conversation_state_updated ON public.ai_conversation_state USING btree (updated_at);


--
-- Name: idx_ai_dim_rel_mappings_dimension_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_dim_rel_mappings_dimension_id ON public.ai_dimension_relationship_mappings USING btree (dimension_id);


--
-- Name: idx_ai_dim_rel_mappings_relationship_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_dim_rel_mappings_relationship_id ON public.ai_dimension_relationship_mappings USING btree (relationship_id);


--
-- Name: idx_ai_instance_dimensions_dimension_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_dimensions_dimension_id ON public.ai_instance_dimensions USING btree (dimension_id);


--
-- Name: idx_ai_instance_dimensions_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_dimensions_instance_id ON public.ai_instance_dimensions USING btree (instance_id);


--
-- Name: idx_ai_instance_memories_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_memories_expires ON public.ai_instance_memories USING btree (memory_type, status, expires_at) WHERE (((memory_type)::text = 'recent'::text) AND (status = 1));


--
-- Name: idx_ai_instance_memories_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_memories_instance_id ON public.ai_instance_memories USING btree (instance_id);


--
-- Name: idx_ai_instance_memories_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_memories_session ON public.ai_instance_memories USING btree (user_qiao_id, instance_qiao_id, status);


--
-- Name: idx_ai_instance_memories_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instance_memories_source ON public.ai_instance_memories USING btree (source_message_id) WHERE (source_message_id IS NOT NULL);


--
-- Name: idx_ai_instances_creation_persona; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_creation_persona ON public.ai_instances USING gin (((creation_metadata -> 'persona_id'::text)));


--
-- Name: idx_ai_instances_llm_config; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_llm_config ON public.ai_instances USING btree (llm_config_id) WHERE (llm_config_id IS NOT NULL);


--
-- Name: idx_ai_instances_persona_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_persona_id ON public.ai_instances USING btree (persona_id) WHERE (persona_id IS NOT NULL);


--
-- Name: idx_ai_instances_personality_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_personality_id ON public.ai_instances USING btree (personality_id);


--
-- Name: idx_ai_instances_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_qiao_id ON public.ai_instances USING btree (qiao_id);


--
-- Name: idx_ai_instances_style_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_style_id ON public.ai_instances USING btree (style_id);


--
-- Name: idx_ai_instances_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_user_id ON public.ai_instances USING btree (user_id);


--
-- Name: idx_ai_instances_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_instances_user_qiao_id ON public.ai_instances USING btree (user_qiao_id);


--
-- Name: idx_ai_message_buffer_expire_scan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_message_buffer_expire_scan ON public.ai_message_buffer USING btree (user_qiao_id, instance_qiao_id, buffer_expires_at_ms) WHERE ((aggregate_state = 1) AND (buffer_expires_at_ms IS NOT NULL));


--
-- Name: idx_ai_message_buffer_macro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_message_buffer_macro ON public.ai_message_buffer USING btree (macro_expires_at_ms) WHERE ((aggregate_state = 1) AND (macro_expires_at_ms IS NOT NULL));


--
-- Name: idx_ai_message_buffer_micro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_message_buffer_micro ON public.ai_message_buffer USING btree (micro_expires_at_ms) WHERE ((aggregate_state = 1) AND (micro_expires_at_ms IS NOT NULL));


--
-- Name: idx_ai_message_buffer_session_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_message_buffer_session_state ON public.ai_message_buffer USING btree (user_qiao_id, instance_qiao_id, aggregate_state);


--
-- Name: idx_ai_personas_ai_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_personas_ai_type ON public.ai_personas USING btree (type_id);


--
-- Name: idx_ai_personas_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_personas_status ON public.ai_personas USING btree (status);


--
-- Name: idx_ai_request_logs_response_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_request_logs_response_id ON public.ai_request_logs USING btree (response_id);


--
-- Name: idx_ai_request_logs_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_request_logs_user_qiao_id ON public.ai_request_logs USING btree (user_qiao_id);


--
-- Name: idx_ai_style_dimensions_dimension_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_style_dimensions_dimension_id ON public.ai_style_dimensions USING btree (dimension_id);


--
-- Name: idx_ai_style_dimensions_style_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_style_dimensions_style_id ON public.ai_style_dimensions USING btree (style_id);


--
-- Name: idx_ai_templates_ai_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_templates_ai_type ON public.ai_templates USING btree (type_id);


--
-- Name: idx_ai_templates_llm_config; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_templates_llm_config ON public.ai_templates USING btree (llm_config_id) WHERE (llm_config_id IS NOT NULL);


--
-- Name: idx_ai_templates_usage; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ai_templates_usage ON public.ai_templates USING btree (type_id, status, is_reusable);


--
-- Name: idx_alert_event_entities_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_event_entities_event_id ON public.alert_event_entities USING btree (event_id);


--
-- Name: idx_alert_event_entities_type_id_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_event_entities_type_id_created_at ON public.alert_event_entities USING btree (entity_type, entity_id, created_at);


--
-- Name: idx_alert_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_events_created_at ON public.alert_events USING btree (created_at);


--
-- Name: idx_alert_events_dedupe_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_events_dedupe_key ON public.alert_events USING btree (dedupe_key);


--
-- Name: idx_alert_events_domain_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_events_domain_created_at ON public.alert_events USING btree (domain, created_at);


--
-- Name: idx_alert_events_event_type_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_alert_events_event_type_created_at ON public.alert_events USING btree (event_type, created_at);


--
-- Name: idx_app_pages_client_locale; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_pages_client_locale ON public.app_pages USING btree (client_type, locale);


--
-- Name: idx_app_pages_page_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_pages_page_key ON public.app_pages USING btree (page_key);


--
-- Name: idx_app_pages_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_app_pages_status ON public.app_pages USING btree (status);


--
-- Name: idx_backup_jobs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backup_jobs_created_at ON public.backup_jobs USING btree (created_at);


--
-- Name: idx_backup_jobs_started_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backup_jobs_started_at ON public.backup_jobs USING btree (started_at);


--
-- Name: idx_backup_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_backup_jobs_status ON public.backup_jobs USING btree (status);


--
-- Name: idx_contact_requests_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contact_requests_expires_at ON public.contact_requests USING btree (expires_at);


--
-- Name: idx_contact_requests_worker_query; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contact_requests_worker_query ON public.contact_requests USING btree (status, to_type, expires_at) WHERE (status = ANY (ARRAY[1, 8]));


--
-- Name: idx_contacts_contact_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_contact_qiao_id ON public.contacts USING btree (contact_qiao_id);


--
-- Name: idx_contacts_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_user_qiao_id ON public.contacts USING btree (user_qiao_id);


--
-- Name: idx_llm_configs_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_llm_configs_provider_id ON public.llm_configs USING btree (provider_id);


--
-- Name: idx_login_records_user_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_login_records_user_token_id ON public.login_records USING btree (user_token_id);


--
-- Name: idx_media_files_file_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_files_file_hash ON public.media_files USING btree (file_hash);


--
-- Name: idx_media_files_file_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_files_file_id ON public.media_files USING btree (file_id);


--
-- Name: idx_media_files_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_files_status ON public.media_files USING btree (status);


--
-- Name: idx_media_files_storage_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_media_files_storage_unique ON public.media_files USING btree (storage_provider, bucket_name, object_key);


--
-- Name: idx_media_files_upload_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_media_files_upload_by ON public.media_files USING btree (upload_by_type, upload_by_id);


--
-- Name: idx_message_deliveries_endpoint_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_deliveries_endpoint_id ON public.message_deliveries USING btree (endpoint_id);


--
-- Name: idx_message_deliveries_msg_id_server; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_deliveries_msg_id_server ON public.message_deliveries USING btree (msg_id_server);


--
-- Name: idx_message_deliveries_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_deliveries_status ON public.message_deliveries USING btree (status);


--
-- Name: idx_message_devices_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_devices_device_id ON public.message_devices USING btree (device_id);


--
-- Name: idx_message_devices_last_acked_msg_sent_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_devices_last_acked_msg_sent_at ON public.message_devices USING btree (last_acked_msg_sent_at);


--
-- Name: idx_message_devices_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_devices_user_qiao_id ON public.message_devices USING btree (user_qiao_id);


--
-- Name: idx_message_dispatch_outbox_owner_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_dispatch_outbox_owner_user_id ON public.message_dispatch_outbox USING btree (owner_user_id);


--
-- Name: idx_message_dispatch_outbox_status_next_retry; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_dispatch_outbox_status_next_retry ON public.message_dispatch_outbox USING btree (status, next_retry_at);


--
-- Name: idx_message_endpoints_device_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_endpoints_device_id ON public.message_endpoints USING btree (device_id);


--
-- Name: idx_message_endpoints_lease_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_endpoints_lease_expires_at ON public.message_endpoints USING btree (lease_expires_at);


--
-- Name: idx_message_endpoints_provider; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_endpoints_provider ON public.message_endpoints USING btree (provider);


--
-- Name: idx_message_endpoints_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_endpoints_scope ON public.message_endpoints USING btree (endpoint_scope);


--
-- Name: idx_message_endpoints_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_endpoints_user_qiao_id ON public.message_endpoints USING btree (user_qiao_id);


--
-- Name: idx_message_history_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_conversation_id ON public.message_history USING btree (conversation_id);


--
-- Name: idx_message_history_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_created_at ON public.message_history USING btree (created_at);


--
-- Name: idx_message_history_from_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_from_qiao_id ON public.message_history USING btree (from_qiao_id);


--
-- Name: idx_message_history_llm_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_llm_request_id ON public.message_history USING btree (llm_request_id);


--
-- Name: idx_message_history_metadata_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_metadata_gin ON public.message_history USING gin (message_metadata);


--
-- Name: idx_message_history_msg_id_client; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_msg_id_client ON public.message_history USING btree (msg_id_client);


--
-- Name: idx_message_history_to_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_message_history_to_qiao_id ON public.message_history USING btree (to_qiao_id);


--
-- Name: idx_notification_push_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notification_push_created_at ON public.notification_push_history USING btree (created_at);


--
-- Name: idx_square_categories_status_sort; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_categories_status_sort ON public.square_categories USING btree (status, sort_order, category_key);


--
-- Name: idx_square_type_entries_ai_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_type_entries_ai_type ON public.square_type_entries USING btree (type_id);


--
-- Name: idx_square_type_entries_category_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_type_entries_category_key ON public.square_type_entries USING btree (category_key);


--
-- Name: idx_square_type_entries_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_square_type_entries_status ON public.square_type_entries USING btree (status);


--
-- Name: idx_template_memories_template; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_template_memories_template ON public.ai_template_memories USING btree (template_id, display_order);


--
-- Name: idx_user_auths_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_auths_user_qiao_id ON public.user_auths USING btree (user_qiao_id);


--
-- Name: idx_user_profile_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profile_logs_created_at ON public.user_profile_logs USING btree (created_at);


--
-- Name: idx_user_profile_logs_field_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profile_logs_field_name ON public.user_profile_logs USING btree (field_name);


--
-- Name: idx_user_profile_logs_modified_by_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profile_logs_modified_by_type ON public.user_profile_logs USING btree (modified_by_type);


--
-- Name: idx_user_profile_logs_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profile_logs_owner_id ON public.user_profile_logs USING btree (owner_id);


--
-- Name: idx_user_profile_logs_owner_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_profile_logs_owner_qiao_id ON public.user_profile_logs USING btree (owner_qiao_id);


--
-- Name: idx_user_tokens_refresh_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_user_tokens_refresh_hash ON public.user_tokens USING btree (refresh_token_hash) WHERE (refresh_token_hash IS NOT NULL);


--
-- Name: idx_user_tokens_user_qiao_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_tokens_user_qiao_id ON public.user_tokens USING btree (user_qiao_id);


--
-- Name: uniq_ai_message_buffer_locked; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_ai_message_buffer_locked ON public.ai_message_buffer USING btree (user_qiao_id, instance_qiao_id) WHERE (aggregate_state = 2);


--
-- Name: uniq_contact_requests_pending_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_contact_requests_pending_pair ON public.contact_requests USING btree (from_qiao_id, to_qiao_id) WHERE (status = ANY (ARRAY[1, 8]));


--
-- Name: uq_ai_instance_memories_content; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ai_instance_memories_content ON public.ai_instance_memories USING btree (instance_id, content);


--
-- Name: uq_ai_personas_username_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ai_personas_username_lower ON public.ai_personas USING btree (lower((username)::text));


--
-- Name: uq_alert_events_event_type_dedupe_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_alert_events_event_type_dedupe_key ON public.alert_events USING btree (event_type, dedupe_key) WHERE (dedupe_key IS NOT NULL);


--
-- Name: uq_message_endpoints_provider_user_device_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_message_endpoints_provider_user_device_scope ON public.message_endpoints USING btree (provider, user_id, device_id) WHERE (endpoint_scope = 2);


--
-- Name: uq_square_type_entries_active_type_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_square_type_entries_active_type_id ON public.square_type_entries USING btree (type_id) WHERE (status = 1);


--
-- Name: uq_users_username_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_username_lower ON public.users USING btree (lower((username)::text)) WHERE (username IS NOT NULL);


--
-- Name: square_categories prevent_square_category_key_update_trigger; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER prevent_square_category_key_update_trigger BEFORE UPDATE ON public.square_categories FOR EACH ROW EXECUTE FUNCTION public.prevent_square_category_key_update();


--
-- Name: ai_instance_memories set_memory_expires_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER set_memory_expires_at BEFORE INSERT OR UPDATE OF importance, refreshed_at, memory_type ON public.ai_instance_memories FOR EACH ROW EXECUTE FUNCTION public.calculate_memory_expires_at();


--
-- Name: admin_users update_admin_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_admin_users_updated_at BEFORE UPDATE ON public.admin_users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_conversation_runtime update_ai_conversation_runtime_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_conversation_runtime_updated_at BEFORE UPDATE ON public.ai_conversation_runtime FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_conversation_state update_ai_conversation_state_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_conversation_state_updated_at BEFORE UPDATE ON public.ai_conversation_state FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_dimension_relationship_mappings update_ai_dimension_relationship_mappings_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_dimension_relationship_mappings_updated_at BEFORE UPDATE ON public.ai_dimension_relationship_mappings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_dimensions update_ai_dimensions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_dimensions_updated_at BEFORE UPDATE ON public.ai_dimensions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_instance_dimensions update_ai_instance_dimensions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_instance_dimensions_updated_at BEFORE UPDATE ON public.ai_instance_dimensions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_instance_memories update_ai_instance_memories_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_instance_memories_updated_at BEFORE UPDATE ON public.ai_instance_memories FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_instances update_ai_instances_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_instances_updated_at BEFORE UPDATE ON public.ai_instances FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_message_buffer update_ai_message_buffer_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_message_buffer_updated_at BEFORE UPDATE ON public.ai_message_buffer FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_personalities update_ai_personalities_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_personalities_updated_at BEFORE UPDATE ON public.ai_personalities FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_personality_placeholders update_ai_personality_placeholders_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_personality_placeholders_updated_at BEFORE UPDATE ON public.ai_personality_placeholders FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_personas update_ai_personas_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_personas_updated_at BEFORE UPDATE ON public.ai_personas FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_relationships update_ai_relationships_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_relationships_updated_at BEFORE UPDATE ON public.ai_relationships FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_style_dimensions update_ai_style_dimensions_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_style_dimensions_updated_at BEFORE UPDATE ON public.ai_style_dimensions FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_styles update_ai_styles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_styles_updated_at BEFORE UPDATE ON public.ai_styles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_template_memories update_ai_template_memories_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_template_memories_updated_at BEFORE UPDATE ON public.ai_template_memories FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_templates update_ai_templates_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_templates_updated_at BEFORE UPDATE ON public.ai_templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_types update_ai_types_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_ai_types_updated_at BEFORE UPDATE ON public.ai_types FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: app_pages update_app_pages_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_app_pages_updated_at BEFORE UPDATE ON public.app_pages FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: backup_jobs update_backup_jobs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_backup_jobs_updated_at BEFORE UPDATE ON public.backup_jobs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: contact_requests update_contact_requests_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_contact_requests_updated_at BEFORE UPDATE ON public.contact_requests FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: contacts update_contacts_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON public.contacts FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: llm_configs update_llm_configs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_llm_configs_updated_at BEFORE UPDATE ON public.llm_configs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: llm_providers update_llm_providers_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_llm_providers_updated_at BEFORE UPDATE ON public.llm_providers FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: media_files update_media_files_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_media_files_updated_at BEFORE UPDATE ON public.media_files FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: message_deliveries update_message_deliveries_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_message_deliveries_updated_at BEFORE UPDATE ON public.message_deliveries FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: message_devices update_message_devices_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_message_devices_updated_at BEFORE UPDATE ON public.message_devices FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: message_dispatch_outbox update_message_dispatch_outbox_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_message_dispatch_outbox_updated_at BEFORE UPDATE ON public.message_dispatch_outbox FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: message_endpoints update_message_endpoints_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_message_endpoints_updated_at BEFORE UPDATE ON public.message_endpoints FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: profiles update_profiles_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: square_type_entries update_square_type_entries_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_square_type_entries_updated_at BEFORE UPDATE ON public.square_type_entries FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: system_configs update_system_configs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_system_configs_updated_at BEFORE UPDATE ON public.system_configs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: user_auths update_user_auths_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_user_auths_updated_at BEFORE UPDATE ON public.user_auths FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: user_risk_stats update_user_risk_stats_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_user_risk_stats_updated_at BEFORE UPDATE ON public.user_risk_stats FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: user_tokens update_user_tokens_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_user_tokens_updated_at BEFORE UPDATE ON public.user_tokens FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: user_violation_logs update_user_violation_logs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_user_violation_logs_updated_at BEFORE UPDATE ON public.user_violation_logs FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: users update_users_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ai_dimension_relationship_mappings fk_ai_dim_rel_mappings_dimension; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimension_relationship_mappings
    ADD CONSTRAINT fk_ai_dim_rel_mappings_dimension FOREIGN KEY (dimension_id) REFERENCES public.ai_dimensions(id) ON DELETE CASCADE;


--
-- Name: ai_dimension_relationship_mappings fk_ai_dim_rel_mappings_relationship; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_dimension_relationship_mappings
    ADD CONSTRAINT fk_ai_dim_rel_mappings_relationship FOREIGN KEY (relationship_id) REFERENCES public.ai_relationships(id) ON DELETE CASCADE;


--
-- Name: ai_instance_dimensions fk_ai_instance_dimensions_dimension; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_dimensions
    ADD CONSTRAINT fk_ai_instance_dimensions_dimension FOREIGN KEY (dimension_id) REFERENCES public.ai_dimensions(id) ON DELETE CASCADE;


--
-- Name: ai_instance_dimensions fk_ai_instance_dimensions_instance; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_dimensions
    ADD CONSTRAINT fk_ai_instance_dimensions_instance FOREIGN KEY (instance_id) REFERENCES public.ai_instances(id) ON DELETE CASCADE;


--
-- Name: ai_instance_memories fk_ai_instance_memories_instance; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_memories
    ADD CONSTRAINT fk_ai_instance_memories_instance FOREIGN KEY (instance_id) REFERENCES public.ai_instances(id) ON DELETE CASCADE;


--
-- Name: ai_instance_memories fk_ai_instance_memories_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instance_memories
    ADD CONSTRAINT fk_ai_instance_memories_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: ai_instances fk_ai_instances_persona; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT fk_ai_instances_persona FOREIGN KEY (persona_id) REFERENCES public.ai_personas(id) ON DELETE RESTRICT;


--
-- Name: ai_instances fk_ai_instances_personality; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT fk_ai_instances_personality FOREIGN KEY (personality_id) REFERENCES public.ai_personalities(id) ON DELETE RESTRICT;


--
-- Name: ai_instances fk_ai_instances_relationship; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT fk_ai_instances_relationship FOREIGN KEY (relationship_id) REFERENCES public.ai_relationships(id) ON DELETE RESTRICT;


--
-- Name: ai_instances fk_ai_instances_style; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT fk_ai_instances_style FOREIGN KEY (style_id) REFERENCES public.ai_styles(id) ON DELETE RESTRICT;


--
-- Name: ai_instances fk_ai_instances_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_instances
    ADD CONSTRAINT fk_ai_instances_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: ai_personality_placeholders fk_ai_personality_placeholders_personality; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personality_placeholders
    ADD CONSTRAINT fk_ai_personality_placeholders_personality FOREIGN KEY (personality_id) REFERENCES public.ai_personalities(id) ON DELETE CASCADE;


--
-- Name: ai_personas fk_ai_personas_type; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_personas
    ADD CONSTRAINT fk_ai_personas_type FOREIGN KEY (type_id) REFERENCES public.ai_types(id) ON DELETE RESTRICT;


--
-- Name: ai_style_dimensions fk_ai_style_dimensions_dimension; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_style_dimensions
    ADD CONSTRAINT fk_ai_style_dimensions_dimension FOREIGN KEY (dimension_id) REFERENCES public.ai_dimensions(id) ON DELETE CASCADE;


--
-- Name: ai_style_dimensions fk_ai_style_dimensions_style; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_style_dimensions
    ADD CONSTRAINT fk_ai_style_dimensions_style FOREIGN KEY (style_id) REFERENCES public.ai_styles(id) ON DELETE CASCADE;


--
-- Name: ai_templates fk_ai_templates_personality; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_templates
    ADD CONSTRAINT fk_ai_templates_personality FOREIGN KEY (personality_id) REFERENCES public.ai_personalities(id) ON DELETE RESTRICT;


--
-- Name: ai_templates fk_ai_templates_style; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_templates
    ADD CONSTRAINT fk_ai_templates_style FOREIGN KEY (style_id) REFERENCES public.ai_styles(id) ON DELETE RESTRICT;


--
-- Name: ai_templates fk_ai_templates_type; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_templates
    ADD CONSTRAINT fk_ai_templates_type FOREIGN KEY (type_id) REFERENCES public.ai_types(id) ON DELETE RESTRICT;


--
-- Name: contacts fk_contacts_custom_avatar_media; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT fk_contacts_custom_avatar_media FOREIGN KEY (custom_avatar_media_id) REFERENCES public.media_files(id) ON DELETE SET NULL;


--
-- Name: contacts fk_contacts_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT fk_contacts_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: llm_configs fk_llm_configs_provider; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.llm_configs
    ADD CONSTRAINT fk_llm_configs_provider FOREIGN KEY (provider_id) REFERENCES public.llm_providers(id) ON DELETE RESTRICT;


--
-- Name: login_records fk_login_records_user_token; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.login_records
    ADD CONSTRAINT fk_login_records_user_token FOREIGN KEY (user_token_id) REFERENCES public.user_tokens(id) ON DELETE SET NULL;


--
-- Name: message_deliveries fk_message_deliveries_endpoint; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_deliveries
    ADD CONSTRAINT fk_message_deliveries_endpoint FOREIGN KEY (endpoint_id) REFERENCES public.message_endpoints(id) ON DELETE CASCADE;


--
-- Name: message_deliveries fk_message_deliveries_message; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_deliveries
    ADD CONSTRAINT fk_message_deliveries_message FOREIGN KEY (msg_id_server) REFERENCES public.message_history(msg_id_server) ON DELETE CASCADE;


--
-- Name: message_devices fk_message_devices_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_devices
    ADD CONSTRAINT fk_message_devices_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: message_dispatch_outbox fk_message_dispatch_outbox_message; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_dispatch_outbox
    ADD CONSTRAINT fk_message_dispatch_outbox_message FOREIGN KEY (msg_id_server) REFERENCES public.message_history(msg_id_server) ON DELETE CASCADE;


--
-- Name: message_dispatch_outbox fk_message_dispatch_outbox_owner_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_dispatch_outbox
    ADD CONSTRAINT fk_message_dispatch_outbox_owner_user FOREIGN KEY (owner_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: message_endpoints fk_message_endpoints_device; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_endpoints
    ADD CONSTRAINT fk_message_endpoints_device FOREIGN KEY (user_id, device_id) REFERENCES public.message_devices(user_id, device_id) ON DELETE CASCADE;


--
-- Name: message_endpoints fk_message_endpoints_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_endpoints
    ADD CONSTRAINT fk_message_endpoints_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: message_history fk_message_history_llm_request; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_history
    ADD CONSTRAINT fk_message_history_llm_request FOREIGN KEY (llm_request_id) REFERENCES public.ai_request_logs(id) ON DELETE SET NULL;


--
-- Name: profiles fk_profiles_avatar_media; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profiles
    ADD CONSTRAINT fk_profiles_avatar_media FOREIGN KEY (avatar_media_id) REFERENCES public.media_files(id) ON DELETE SET NULL;


--
-- Name: square_type_entries fk_square_type_entries_category; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_type_entries
    ADD CONSTRAINT fk_square_type_entries_category FOREIGN KEY (category_key) REFERENCES public.square_categories(category_key) ON DELETE RESTRICT;


--
-- Name: square_type_entries fk_square_type_entries_type; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.square_type_entries
    ADD CONSTRAINT fk_square_type_entries_type FOREIGN KEY (type_id) REFERENCES public.ai_types(id) ON DELETE RESTRICT;


--
-- Name: ai_template_memories fk_template_memories_template; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_template_memories
    ADD CONSTRAINT fk_template_memories_template FOREIGN KEY (template_id) REFERENCES public.ai_templates(id) ON DELETE CASCADE;


--
-- Name: user_auths fk_user_auths_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_auths
    ADD CONSTRAINT fk_user_auths_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_tokens fk_user_tokens_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_tokens
    ADD CONSTRAINT fk_user_tokens_user FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict says123
