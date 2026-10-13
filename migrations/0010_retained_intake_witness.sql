-- Retained first-party intake witnesses: original metadata plus immutable typed closure.
-- Existing migrations and evidence rows are unchanged. A witness grants no source authority.

ALTER TABLE eqos.evidence_inputs DROP CONSTRAINT evidence_inputs_kind_check;
ALTER TABLE eqos.evidence_inputs ADD CONSTRAINT evidence_inputs_kind_check CHECK (
    kind IN ('ENTITY_MAP', 'ISSUER_IDENTITY', 'ISSUER_CONFIG', 'RETAINED_INTAKE'));

CREATE FUNCTION eqos.retained_intake_safe_label(value text) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
    SELECT value<>'' AND value!~'^/|/$|//|(^|/)\.{1,2}(/|$)'
        AND strpos(value,chr(92))=0 AND value!~E'[\t\n\r]'
$$;

-- Match Python json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=True).
-- Witness numeric fields are integers; old values and embedded contexts are strings.
CREATE FUNCTION eqos.retained_intake_json(document jsonb) RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
DECLARE
    result text;
    character text;
    code integer;
BEGIN
    CASE jsonb_typeof(document)
    WHEN 'object' THEN
        SELECT '{'||coalesce(string_agg(eqos.retained_intake_json(to_jsonb(key))||':'||
            eqos.retained_intake_json(value),',' ORDER BY key COLLATE "C"),'')||'}'
        INTO result FROM jsonb_each(document);
    WHEN 'array' THEN
        SELECT '['||coalesce(string_agg(eqos.retained_intake_json(value),',' ORDER BY ordinal),'')||']'
        INTO result FROM jsonb_array_elements(document) WITH ORDINALITY AS entries(value,ordinal);
    WHEN 'string' THEN
        result:='';
        FOR character IN SELECT ch FROM regexp_split_to_table(document::text,'') AS chars(ch) LOOP
            code:=ascii(character);
            IF code<127 THEN
                result:=result||character;
            ELSIF code<=65535 THEN
                result:=result||chr(92)||'u'||lpad(to_hex(code),4,'0');
            ELSE
                code:=code-65536;
                result:=result||chr(92)||'u'||to_hex(55296+(code/1024))||
                    chr(92)||'u'||to_hex(56320+(code%1024));
            END IF;
        END LOOP;
    ELSE result:=document::text;
    END CASE;
    RETURN result;
END $$;

CREATE FUNCTION eqos.retained_intake_hash(document jsonb) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
    SELECT encode(sha256(convert_to(eqos.retained_intake_json(document),'UTF8')),'hex')
$$;

CREATE FUNCTION eqos.retained_intake_iso_utc(value timestamptz) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE SET search_path=pg_catalog AS $$
    SELECT to_char(value AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')||
        CASE WHEN extract(microseconds FROM value)::bigint%1000000=0 THEN ''
             ELSE '.'||to_char(value AT TIME ZONE 'UTC','US') END||'+00:00'
$$;

CREATE FUNCTION eqos.retained_intake_filed_at(value text) RETURNS timestamptz
LANGUAGE plpgsql STABLE STRICT SET search_path=pg_catalog AS $$
DECLARE month_number integer;
BEGIN
    IF value~'^\d{2}-[A-Z][a-z]{2}-\d{4} \d{2}:\d{2}:\d{2}$' THEN
        month_number:=array_position(ARRAY['Jan','Feb','Mar','Apr','May','Jun',
            'Jul','Aug','Sep','Oct','Nov','Dec'],substring(value FROM 4 FOR 3));
        IF month_number IS NULL THEN
            RAISE EXCEPTION 'retained intake filed-at month is invalid' USING ERRCODE='23514';
        END IF;
        RETURN make_timestamp(substring(value FROM 8 FOR 4)::integer,month_number,
            substring(value FROM 1 FOR 2)::integer,substring(value FROM 13 FOR 2)::integer,
            substring(value FROM 16 FOR 2)::integer,substring(value FROM 19 FOR 2)::integer)
            AT TIME ZONE 'Asia/Kolkata';
    ELSIF value~'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?[+-]\d{2}:\d{2}$' THEN
        RETURN value::timestamptz;
    END IF;
    RAISE EXCEPTION 'retained intake filed-at requires an evidenced offset or NSE wall time'
        USING ERRCODE='23514';
END $$;

CREATE TABLE eqos.retained_intake_witnesses (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    evidence_input_id bigint NOT NULL UNIQUE REFERENCES eqos.evidence_inputs(id),
    schema_version text NOT NULL CHECK(schema_version='retained_intake_v1'),
    issuer text NOT NULL CHECK(issuer~'^[A-Z0-9][A-Z0-9_-]*$'),
    quarter text NOT NULL CHECK(quarter~'^[A-Z0-9][A-Z0-9_-]*$'),
    manifest_body bytea NOT NULL,
    manifest_sha256 text NOT NULL CHECK(manifest_sha256~'^[0-9a-f]{64}$'),
    manifest_size integer NOT NULL CHECK(manifest_size BETWEEN 1 AND 1048576),
    manifest_label text NOT NULL CHECK(eqos.retained_intake_safe_label(manifest_label)),
    issuer_config_body bytea NOT NULL,
    issuer_config_sha256 text NOT NULL CHECK(issuer_config_sha256~'^[0-9a-f]{64}$'),
    issuer_config_size integer NOT NULL CHECK(issuer_config_size BETWEEN 1 AND 1048576),
    issuer_config_label text NOT NULL CHECK(eqos.retained_intake_safe_label(issuer_config_label)),
    selection_json jsonb NOT NULL CHECK(jsonb_typeof(selection_json)='array'),
    entity_id bigint NOT NULL REFERENCES eqos.reporting_entities(id),
    family text NOT NULL CHECK(family IN ('FINANCIAL_RESULTS','SHAREHOLDING')),
    period_end date NOT NULL,
    basis text NOT NULL CHECK(basis IN ('CONSOLIDATED','STANDALONE')),
    framework text NOT NULL CHECK(framework IN ('IND_AS','IFRS','US_GAAP','UNKNOWN')),
    package_id bigint NOT NULL REFERENCES eqos.filing_packages(id),
    package_evidence_sha256 text NOT NULL CHECK(package_evidence_sha256~'^[0-9a-f]{64}$'),
    settings_record_id bigint NOT NULL REFERENCES eqos.settings_records(id),
    qualification_context_sha256 text NOT NULL CHECK(qualification_context_sha256~'^[0-9a-f]{64}$'),
    publication_version text NOT NULL CHECK(publication_version<>''),
    publication_sha256 text NOT NULL CHECK(publication_sha256~'^[0-9a-f]{64}$'),
    publication_state text NOT NULL CHECK(publication_state IN ('RELEASED','SYNTHETIC')),
    canonical_payload jsonb NOT NULL CHECK(jsonb_typeof(canonical_payload)='object'),
    content_sha256 text NOT NULL CHECK(content_sha256~'^[0-9a-f]{64}$'),
    CHECK(octet_length(manifest_body)=manifest_size),
    CHECK(encode(sha256(manifest_body),'hex')=manifest_sha256),
    CHECK(octet_length(issuer_config_body)=issuer_config_size),
    CHECK(encode(sha256(issuer_config_body),'hex')=issuer_config_sha256)
);

CREATE TABLE eqos.retained_intake_witness_bindings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    witness_id bigint NOT NULL REFERENCES eqos.retained_intake_witnesses(id),
    representation text NOT NULL CHECK(representation IN ('XBRL','PDF')),
    source_id text NOT NULL CHECK(source_id<>''),
    surface text NOT NULL,
    relative_path text NOT NULL CHECK(eqos.retained_intake_safe_label(relative_path)),
    expected_input_sha256 text NOT NULL CHECK(expected_input_sha256~'^[0-9a-f]{64}$'),
    request_key text NOT NULL CHECK(request_key~'^[0-9a-f]{64}$'),
    filed_at_raw text NOT NULL CHECK(filed_at_raw<>''),
    knowledge_time timestamptz NOT NULL,
    extractor_version text NOT NULL CHECK(extractor_version<>''),
    extractor_sha256 text NOT NULL CHECK(extractor_sha256~'^[0-9a-f]{64}$'),
    extraction_context_sha256 text CHECK(extraction_context_sha256~'^[0-9a-f]{64}$'),
    context_material jsonb NOT NULL CHECK(jsonb_typeof(context_material)='object'),
    UNIQUE(witness_id,representation), UNIQUE(witness_id,id),
    CHECK((representation='XBRL' AND surface='NSE_XBRL_INSTANCE') OR
          (representation='PDF' AND surface='NSE_RESULTS_PDF')),
    CHECK(knowledge_time=eqos.retained_intake_filed_at(filed_at_raw)),
    CHECK(extraction_context_sha256 IS NOT NULL AND
        extraction_context_sha256=eqos.retained_intake_hash(context_material)),
    CHECK(request_key=eqos.retained_intake_hash(jsonb_build_object(
        'representation',representation,'sha256',expected_input_sha256)))
);

CREATE TABLE eqos.retained_intake_witness_attempts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    witness_id bigint NOT NULL REFERENCES eqos.retained_intake_witnesses(id),
    binding_id bigint NOT NULL,
    attempt_id bigint NOT NULL REFERENCES eqos.acquisition_attempts(id),
    FOREIGN KEY(witness_id,binding_id) REFERENCES eqos.retained_intake_witness_bindings(witness_id,id),
    UNIQUE(witness_id,attempt_id)
);

CREATE TABLE eqos.retained_intake_witness_captures (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    witness_id bigint NOT NULL REFERENCES eqos.retained_intake_witnesses(id),
    binding_id bigint NOT NULL,
    capture_ref_id bigint NOT NULL REFERENCES eqos.capture_refs(id),
    disposition text NOT NULL CHECK(disposition IN ('PACKAGE_MEMBER','FAILED_PEER')),
    FOREIGN KEY(witness_id,binding_id) REFERENCES eqos.retained_intake_witness_bindings(witness_id,id),
    UNIQUE(witness_id,capture_ref_id)
);

CREATE TABLE eqos.retained_intake_witness_pins (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    witness_id bigint NOT NULL REFERENCES eqos.retained_intake_witnesses(id),
    artifact text NOT NULL CHECK(artifact<>'' AND artifact!~E'[\t\n\r]'),
    version_pin_id bigint NOT NULL REFERENCES eqos.version_pins(id),
    UNIQUE(witness_id,artifact)
);

CREATE TABLE eqos.retained_intake_witness_seals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY CHECK(id>0),
    witness_id bigint NOT NULL UNIQUE REFERENCES eqos.retained_intake_witnesses(id),
    closure_sha256 text NOT NULL CHECK(closure_sha256~'^[0-9a-f]{64}$'),
    binding_count integer NOT NULL CHECK(binding_count BETWEEN 1 AND 2),
    attempt_count integer NOT NULL CHECK(attempt_count>0),
    capture_count integer NOT NULL CHECK(capture_count>0),
    pin_count integer NOT NULL CHECK(pin_count>0),
    sealed_at timestamptz NOT NULL
);

CREATE FUNCTION eqos.require_retained_intake_read_committed() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF current_setting('transaction_isolation')<>'read committed' THEN
        RAISE EXCEPTION 'retained intake writes require READ COMMITTED' USING ERRCODE='25001';
    END IF;
END $$;

CREATE FUNCTION eqos.lock_unsealed_retained_intake(evidence_id bigint) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    PERFORM eqos.require_retained_intake_read_committed();
    IF evidence_id IS NULL OR evidence_id<=0 THEN
        RAISE EXCEPTION 'retained intake evidence identity is missing' USING ERRCODE='23503';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('retained-intake-evidence:'||evidence_id::text,0));
    -- VOLATILE + READ COMMITTED obtains a new snapshot after any lock wait.
    IF EXISTS(SELECT 1 FROM eqos.retained_intake_witness_seals s
        JOIN eqos.retained_intake_witnesses w ON w.id=s.witness_id
        WHERE w.evidence_input_id=evidence_id) THEN
        RAISE EXCEPTION 'retained intake witness is already sealed' USING ERRCODE='23514';
    END IF;
END $$;

CREATE FUNCTION eqos.guard_retained_intake_evidence_input() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.kind='RETAINED_INTAKE' THEN
        PERFORM eqos.require_retained_intake_read_committed();
        PERFORM eqos.lock_unsealed_retained_intake(NEW.id);
        IF NEW.label!~'^retained_intake_v1:[A-Z0-9][A-Z0-9_-]*:[A-Z0-9][A-Z0-9_-]*$'
           OR NEW.content_sha256!~'^[0-9a-f]{64}$'
           OR NEW.recorded_at IS DISTINCT FROM eqos.store_now() THEN
            RAISE EXCEPTION 'retained intake evidence kind/label/content/store clock differs'
                USING ERRCODE='23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER guard_retained_intake_evidence_input BEFORE INSERT ON eqos.evidence_inputs
FOR EACH ROW EXECUTE FUNCTION eqos.guard_retained_intake_evidence_input();

CREATE FUNCTION eqos.guard_retained_intake_statement() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    PERFORM eqos.require_retained_intake_read_committed();
    RETURN NULL;
END $$;

CREATE FUNCTION eqos.guard_retained_intake_header() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    prepared jsonb;
    input eqos.evidence_inputs%ROWTYPE;
BEGIN
    PERFORM eqos.require_retained_intake_read_committed();
    PERFORM eqos.lock_unsealed_retained_intake(NEW.evidence_input_id);
    SELECT * INTO input FROM eqos.evidence_inputs WHERE id=NEW.evidence_input_id;
    IF NOT FOUND OR input.kind<>'RETAINED_INTAKE'
       OR input.label IS DISTINCT FROM NEW.schema_version||':'||NEW.issuer||':'||NEW.quarter
       OR input.content_sha256 IS DISTINCT FROM NEW.content_sha256
       OR input.recorded_at IS DISTINCT FROM eqos.store_now() THEN
        RAISE EXCEPTION 'retained intake header differs from its new evidence input'
            USING ERRCODE='23514';
    END IF;
    prepared:=NEW.canonical_payload->'prepared';
    IF prepared->>'schema_version' IS DISTINCT FROM NEW.schema_version
       OR prepared->>'issuer' IS DISTINCT FROM NEW.issuer
       OR prepared->>'quarter' IS DISTINCT FROM NEW.quarter
       OR prepared->'selection' IS DISTINCT FROM NEW.selection_json
       OR prepared->'entity_id' IS DISTINCT FROM to_jsonb(NEW.entity_id)
       OR prepared->>'family' IS DISTINCT FROM NEW.family
       OR prepared->>'reporting_period_end' IS DISTINCT FROM NEW.period_end::text
       OR prepared->>'basis' IS DISTINCT FROM NEW.basis
       OR prepared->>'framework' IS DISTINCT FROM NEW.framework
       OR prepared->'manifest' IS DISTINCT FROM jsonb_build_object('label',NEW.manifest_label,
            'body',translate(replace(encode(NEW.manifest_body,'base64'),E'\n',''),'+/','-_'),
            'sha256',NEW.manifest_sha256,'size',NEW.manifest_size)
       OR prepared->'issuer_config' IS DISTINCT FROM jsonb_build_object('label',NEW.issuer_config_label,
            'body',translate(replace(encode(NEW.issuer_config_body,'base64'),E'\n',''),'+/','-_'),
            'sha256',NEW.issuer_config_sha256,'size',NEW.issuer_config_size)
       OR NEW.canonical_payload->'package_id' IS DISTINCT FROM to_jsonb(NEW.package_id)
       OR NEW.canonical_payload->>'package_evidence_sha256' IS DISTINCT FROM NEW.package_evidence_sha256
       OR NEW.canonical_payload->'settings_record_id' IS DISTINCT FROM to_jsonb(NEW.settings_record_id)
       OR NEW.canonical_payload->>'qualification_context_sha256' IS DISTINCT FROM NEW.qualification_context_sha256
       OR NEW.canonical_payload->>'publication_version' IS DISTINCT FROM NEW.publication_version
       OR NEW.canonical_payload->>'publication_sha256' IS DISTINCT FROM NEW.publication_sha256
       OR NEW.canonical_payload->>'publication_state' IS DISTINCT FROM NEW.publication_state
       OR eqos.retained_intake_hash((NEW.canonical_payload#-'{prepared,manifest,body}')
            #-'{prepared,issuer_config,body}') IS DISTINCT FROM NEW.content_sha256 THEN
        RAISE EXCEPTION 'retained intake canonical payload differs from typed header/material/hash'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION eqos.guard_retained_intake_child() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE evidence_id bigint;
BEGIN
    PERFORM eqos.require_retained_intake_read_committed();
    SELECT evidence_input_id INTO evidence_id FROM eqos.retained_intake_witnesses
        WHERE id=NEW.witness_id;
    PERFORM eqos.lock_unsealed_retained_intake(evidence_id);
    RETURN NEW;
END $$;

CREATE FUNCTION eqos.guard_retained_intake_seal() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    header eqos.retained_intake_witnesses%ROWTYPE;
    input eqos.evidence_inputs%ROWTYPE;
    setting eqos.settings_records%ROWTYPE;
    binding eqos.retained_intake_witness_bindings%ROWTYPE;
    attempt eqos.acquisition_attempts%ROWTYPE;
    capture eqos.capture_refs%ROWTYPE;
    pin eqos.version_pins%ROWTYPE;
    material jsonb;
    generation jsonb;
    expected jsonb;
    candidate jsonb;
    entry jsonb;
    selection_kind text;
    evidence_id bigint;
    row_count integer;
    total integer;
    seal_time timestamptz;
    closure text;
BEGIN
    PERFORM eqos.require_retained_intake_read_committed();
    SELECT evidence_input_id INTO evidence_id FROM eqos.retained_intake_witnesses
        WHERE id=NEW.witness_id;
    PERFORM eqos.lock_unsealed_retained_intake(evidence_id);
    SELECT * INTO header FROM eqos.retained_intake_witnesses WHERE id=NEW.witness_id;
    SELECT * INTO input FROM eqos.evidence_inputs WHERE id=evidence_id;
    seal_time:=eqos.store_now();
    IF NEW.sealed_at IS NOT NULL AND NEW.sealed_at IS DISTINCT FROM seal_time THEN
        RAISE EXCEPTION 'retained intake seal rejects a caller clock' USING ERRCODE='23514';
    END IF;
    NEW.sealed_at:=seal_time;
    IF input.kind<>'RETAINED_INTAKE' OR input.recorded_at IS DISTINCT FROM seal_time
       OR input.label IS DISTINCT FROM header.schema_version||':'||header.issuer||':'||header.quarter
       OR input.content_sha256 IS DISTINCT FROM header.content_sha256 THEN
        RAISE EXCEPTION 'retained intake seal/evidence identity or transaction clock differs'
            USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS(SELECT 1 FROM eqos.filing_packages p WHERE p.id=header.package_id
        AND (p.entity_id,p.family,p.reporting_period_end,p.basis,p.framework,p.evidence_sha256)
          =(header.entity_id,header.family,header.period_end,header.basis,header.framework,
            header.package_evidence_sha256) AND p.knowledge_time<=seal_time)
       OR NOT EXISTS(SELECT 1 FROM eqos.reporting_entities e
            WHERE e.id=header.entity_id AND e.entity_key=header.issuer) THEN
        RAISE EXCEPTION 'retained intake package scope/hash/issuer differs' USING ERRCODE='23514';
    END IF;
    generation:=(header.canonical_payload->>'generation_json')::jsonb;
    IF eqos.retained_intake_json(generation) IS DISTINCT FROM header.canonical_payload->>'generation_json'
       OR generation?'retained_intake_witness_id'
       OR generation->'package_id' IS DISTINCT FROM to_jsonb(header.package_id)
       OR generation->>'package_evidence_sha256' IS DISTINCT FROM header.package_evidence_sha256
       OR generation->'entity_id' IS DISTINCT FROM to_jsonb(header.entity_id)
       OR generation->>'family' IS DISTINCT FROM header.family
       OR generation->>'reporting_period_end' IS DISTINCT FROM header.period_end::text
       OR generation->>'basis' IS DISTINCT FROM header.basis
       OR generation->>'framework' IS DISTINCT FROM header.framework
       OR generation->>'publication_version' IS DISTINCT FROM header.publication_version
       OR generation->>'publication_sha256' IS DISTINCT FROM header.publication_sha256
       OR generation->>'publication_state' IS DISTINCT FROM header.publication_state
       OR generation->>'qualification_context_sha256' IS DISTINCT FROM header.qualification_context_sha256 THEN
        RAISE EXCEPTION 'retained intake generation scope/publication projection differs'
            USING ERRCODE='23514';
    END IF;
    SELECT * INTO setting FROM eqos.settings_records WHERE id=header.settings_record_id;
    IF setting.entity_id IS DISTINCT FROM header.entity_id
       OR setting.setting_key IS DISTINCT FROM 'FISCAL_YEAR_END_MONTH'
       OR setting.value_text!~'^(0?[1-9]|1[0-2])$' OR setting.recorded_at>seal_time
       OR generation->'fiscal_year_end_setting_id' IS DISTINCT FROM to_jsonb(setting.id)
       OR generation->'fiscal_year_end_setting_evidence_input_id' IS DISTINCT FROM to_jsonb(setting.evidence_input_id)
       OR (generation->>'fiscal_year_end_setting_recorded_at')::timestamptz IS DISTINCT FROM setting.recorded_at
       OR generation->'fiscal_year_end_month' IS DISTINCT FROM to_jsonb(setting.value_text::integer)
       OR eqos.retained_intake_hash(jsonb_build_object('settings_record_id',setting.id,
            'entity_id',setting.entity_id,'setting_key',setting.setting_key,'value_text',setting.value_text,
            'evidence_input_id',setting.evidence_input_id,
            'recorded_at',eqos.retained_intake_iso_utc(setting.recorded_at)))
            IS DISTINCT FROM header.qualification_context_sha256 THEN
        RAISE EXCEPTION 'retained intake qualification setting differs' USING ERRCODE='23514';
    END IF;
    material:=convert_from(header.manifest_body,'UTF8')::jsonb;
    IF material->>'issuer' IS DISTINCT FROM header.issuer
       OR material->>'authorization' IS DISTINCT FROM header.canonical_payload#>>'{prepared,authority_ref}'
       OR coalesce(material->>'authorization','')='' THEN
        RAISE EXCEPTION 'retained intake manifest scope differs' USING ERRCODE='23514';
    END IF;
    SELECT count(*) INTO total FROM eqos.retained_intake_witness_bindings WHERE witness_id=header.id;
    IF total<>NEW.binding_count OR total<>jsonb_array_length(header.selection_json)
       OR total<>jsonb_array_length(header.canonical_payload#>'{prepared,requests}')
       OR total<>jsonb_array_length(header.canonical_payload->'associations') THEN
        RAISE EXCEPTION 'retained intake binding/selection counts differ' USING ERRCODE='23514';
    END IF;
    SELECT jsonb_agg(representation ORDER BY representation COLLATE "C") INTO expected
        FROM eqos.retained_intake_witness_bindings WHERE witness_id=header.id;
    IF expected IS DISTINCT FROM (SELECT jsonb_agg(item->'representation' ORDER BY ordinal)
            FROM jsonb_array_elements(header.selection_json) WITH ORDINALITY AS rows(item,ordinal))
       OR expected IS DISTINCT FROM (SELECT jsonb_agg(item->'representation' ORDER BY ordinal)
            FROM jsonb_array_elements(header.canonical_payload#>'{prepared,requests}')
                WITH ORDINALITY AS rows(item,ordinal))
       OR expected IS DISTINCT FROM (SELECT jsonb_agg(item->'representation' ORDER BY ordinal)
            FROM jsonb_array_elements(header.canonical_payload->'associations')
                WITH ORDINALITY AS rows(item,ordinal)) THEN
        RAISE EXCEPTION 'retained intake request order or representation closure differs'
            USING ERRCODE='23514';
    END IF;
    FOR binding IN SELECT * FROM eqos.retained_intake_witness_bindings
        WHERE witness_id=header.id ORDER BY representation COLLATE "C" LOOP
        SELECT count(*),min(item->>'kind') INTO row_count,selection_kind
        FROM jsonb_array_elements(header.selection_json) AS selected(item)
        WHERE item->>'representation'=binding.representation;
        IF row_count<>1 OR coalesce(selection_kind,'')=''
           OR (selection_kind LIKE 'xbrl-%') IS DISTINCT FROM (binding.representation='XBRL') THEN
            RAISE EXCEPTION 'retained intake selector differs from its binding' USING ERRCODE='23514';
        END IF;
        SELECT count(*) INTO row_count FROM jsonb_array_elements(material->'entries') AS entries(item)
            WHERE item->>'quarter'=header.quarter AND item->>'kind'=selection_kind;
        SELECT item INTO entry FROM jsonb_array_elements(material->'entries') AS entries(item)
            WHERE item->>'quarter'=header.quarter AND item->>'kind'=selection_kind LIMIT 1;
        IF row_count<>1 OR NOT eqos.retained_intake_safe_label(entry->>'filename')
           OR strpos(entry->>'filename','/')<>0
           OR binding.relative_path IS DISTINCT FROM
                ((CASE binding.representation WHEN 'XBRL' THEN 'nse/' ELSE 'nse_pdf/' END)||
                (entry->>'filename'))
           OR binding.expected_input_sha256 IS DISTINCT FROM entry->>'sha256'
           OR binding.filed_at_raw IS DISTINCT FROM entry->>'filed_at_nse'
           OR binding.knowledge_time>seal_time
           OR binding.source_id IS DISTINCT FROM (CASE binding.representation
                WHEN 'XBRL' THEN 'nse-indas-xbrl-consolidated'
                ELSE header.canonical_payload#>>'{prepared,results_pdf_source_id}' END) THEN
            RAISE EXCEPTION 'retained intake binding differs from original manifest input'
                USING ERRCODE='23514';
        END IF;
        SELECT item INTO candidate FROM jsonb_array_elements(header.canonical_payload#>'{prepared,requests}')
            AS requests(item) WHERE item->>'representation'=binding.representation;
        expected:=jsonb_build_object('representation',binding.representation,'source_id',binding.source_id,
            'surface',binding.surface,'relative_path',binding.relative_path,
            'expected_input_sha256',binding.expected_input_sha256,'request_key',binding.request_key,
            'filed_at_raw',binding.filed_at_raw,'extractor_pin',jsonb_build_object(
                'version',binding.extractor_version,'content_sha256',binding.extractor_sha256),
            'extraction_context_sha256',binding.extraction_context_sha256,
            'context_material_json',eqos.retained_intake_json(binding.context_material));
        IF candidate-'knowledge_time' IS DISTINCT FROM expected
           OR (candidate->>'knowledge_time')::timestamptz IS DISTINCT FROM binding.knowledge_time THEN
            RAISE EXCEPTION 'retained intake canonical request differs from typed binding'
                USING ERRCODE='23514';
        END IF;
        IF binding.representation='XBRL' AND binding.context_material IS DISTINCT FROM
            jsonb_build_object('mapping_set_version',generation#>>'{mapping_set_pin,version}') THEN
            RAISE EXCEPTION 'retained intake XBRL decision context differs from mapping pin'
                USING ERRCODE='23514';
        END IF;
        SELECT jsonb_build_object('representation',binding.representation,
            'attempt_ids',coalesce((SELECT jsonb_agg(a.attempt_id ORDER BY a.attempt_id)
                FROM eqos.retained_intake_witness_attempts a WHERE a.witness_id=header.id
                    AND a.binding_id=binding.id),'[]'::jsonb),
            'package_capture_ids',coalesce((SELECT jsonb_agg(c.capture_ref_id ORDER BY c.capture_ref_id)
                FROM eqos.retained_intake_witness_captures c WHERE c.witness_id=header.id
                    AND c.binding_id=binding.id AND c.disposition='PACKAGE_MEMBER'),'[]'::jsonb),
            'failed_capture_ids',coalesce((SELECT jsonb_agg(c.capture_ref_id ORDER BY c.capture_ref_id)
                FROM eqos.retained_intake_witness_captures c WHERE c.witness_id=header.id
                    AND c.binding_id=binding.id AND c.disposition='FAILED_PEER'),'[]'::jsonb)) INTO expected;
        SELECT item INTO candidate FROM jsonb_array_elements(header.canonical_payload->'associations')
            AS associations(item) WHERE item->>'representation'=binding.representation;
        IF candidate IS DISTINCT FROM expected OR jsonb_array_length(expected->'attempt_ids')=0 THEN
            RAISE EXCEPTION 'retained intake normalized association differs' USING ERRCODE='23514';
        END IF;
    END LOOP;
    SELECT count(*),coalesce(jsonb_agg(a.attempt_id ORDER BY a.attempt_id),'[]'::jsonb)
        INTO total,expected FROM eqos.retained_intake_witness_attempts a WHERE a.witness_id=header.id;
    IF total<>NEW.attempt_count OR total<>jsonb_array_length(header.canonical_payload->'attempts')
       OR expected IS DISTINCT FROM generation->'attempt_ids'
       OR expected IS DISTINCT FROM (SELECT jsonb_agg(item->'attempt_id' ORDER BY ordinal)
            FROM jsonb_array_elements(header.canonical_payload->'attempts')
                WITH ORDINALITY AS rows(item,ordinal)) THEN
        RAISE EXCEPTION 'retained intake complete generation attempts differ' USING ERRCODE='23514';
    END IF;
    FOR candidate IN SELECT item FROM jsonb_array_elements(header.canonical_payload->'attempts') AS rows(item) LOOP
        SELECT a.* INTO attempt FROM eqos.retained_intake_witness_attempts link
            JOIN eqos.acquisition_attempts a ON a.id=link.attempt_id
            WHERE link.witness_id=header.id AND link.attempt_id=(candidate->>'attempt_id')::bigint;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'retained intake canonical attempt is not linked' USING ERRCODE='23514';
        END IF;
        SELECT b.* INTO binding FROM eqos.retained_intake_witness_attempts link
            JOIN eqos.retained_intake_witness_bindings b ON b.id=link.binding_id
            WHERE link.witness_id=header.id AND link.attempt_id=attempt.id;
        IF candidate-'attempt_id'-'capture'-'attempted_at' IS DISTINCT FROM
                to_jsonb(attempt)-'id'-'capture_ref_id'-'attempted_at'
           OR (candidate->>'attempted_at')::timestamptz IS DISTINCT FROM attempt.attempted_at
           OR attempt.attempted_at>seal_time
           OR (attempt.source_id,attempt.surface,attempt.entity_id,attempt.period_end,
                attempt.basis,attempt.framework,attempt.representation,attempt.input_sha256)
              IS DISTINCT FROM (binding.source_id,binding.surface,header.entity_id,header.period_end,
                header.basis,header.framework,binding.representation,binding.expected_input_sha256)
           OR attempt.package_id IS NOT NULL AND attempt.package_id<>header.package_id
           OR attempt.stage='ACQUISITION' AND (attempt.capture_ref_id IS NOT NULL
                OR attempt.package_id IS NOT NULL OR attempt.statement_family IS NOT NULL
                OR attempt.extractor_version<>'' OR attempt.extraction_context_sha256 IS NOT NULL
                OR attempt.outcome NOT IN ('FAILED','NOT_AUTHORISED'))
           OR attempt.stage='EXTRACTION' AND (attempt.capture_ref_id IS NULL
                OR attempt.extractor_version<>binding.extractor_version
                OR attempt.extraction_context_sha256 IS DISTINCT FROM (CASE
                    WHEN binding.representation='PDF' OR attempt.outcome='UNSUPPORTED_SCHEMA'
                    THEN binding.extraction_context_sha256 ELSE NULL END)) THEN
            RAISE EXCEPTION 'retained intake attempt scope/payload/context/clock differs'
                USING ERRCODE='23514';
        END IF;
        IF attempt.capture_ref_id IS NULL THEN
            IF candidate->'capture' IS DISTINCT FROM 'null'::jsonb THEN
                RAISE EXCEPTION 'retained intake acquisition fabricates a capture' USING ERRCODE='23514';
            END IF;
        ELSE
            SELECT * INTO capture FROM eqos.capture_refs WHERE id=attempt.capture_ref_id;
            IF (candidate->'capture')-'capture_ref_id'-'registered_at'-'first_seen_at' IS DISTINCT FROM
                    to_jsonb(capture)-'id'-'registered_at'-'first_seen_at'
               OR candidate#>'{capture,capture_ref_id}' IS DISTINCT FROM to_jsonb(capture.id)
               OR (candidate#>>'{capture,registered_at}')::timestamptz IS DISTINCT FROM capture.registered_at
               OR (candidate#>>'{capture,first_seen_at}')::timestamptz IS DISTINCT FROM capture.first_seen_at
               OR NOT EXISTS(SELECT 1 FROM eqos.retained_intake_witness_captures c
                    WHERE c.witness_id=header.id AND c.binding_id=binding.id AND c.capture_ref_id=capture.id) THEN
                RAISE EXCEPTION 'retained intake attempt capture payload differs' USING ERRCODE='23514';
            END IF;
        END IF;
    END LOOP;
    SELECT count(*),jsonb_agg(capture_ref_id ORDER BY capture_ref_id) INTO total,expected
        FROM eqos.retained_intake_witness_captures WHERE witness_id=header.id;
    IF total<>NEW.capture_count OR total<>jsonb_array_length(header.canonical_payload->'captures')
       OR expected IS DISTINCT FROM (SELECT jsonb_agg(item->'capture_ref_id' ORDER BY ordinal)
            FROM jsonb_array_elements(header.canonical_payload->'captures')
                WITH ORDINALITY AS rows(item,ordinal)) THEN
        RAISE EXCEPTION 'retained intake capture counts differ' USING ERRCODE='23514';
    END IF;
    FOR candidate IN SELECT item FROM jsonb_array_elements(header.canonical_payload->'captures') AS rows(item) LOOP
        SELECT c.* INTO capture FROM eqos.retained_intake_witness_captures link
            JOIN eqos.capture_refs c ON c.id=link.capture_ref_id
            WHERE link.witness_id=header.id AND link.capture_ref_id=(candidate->>'capture_ref_id')::bigint;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'retained intake canonical capture is not linked' USING ERRCODE='23514';
        END IF;
        SELECT b.* INTO binding FROM eqos.retained_intake_witness_captures link
            JOIN eqos.retained_intake_witness_bindings b ON b.id=link.binding_id
            WHERE link.witness_id=header.id AND link.capture_ref_id=capture.id;
        IF candidate-'capture_ref_id'-'registered_at'-'first_seen_at' IS DISTINCT FROM
                to_jsonb(capture)-'id'-'registered_at'-'first_seen_at'
           OR (candidate->>'registered_at')::timestamptz IS DISTINCT FROM capture.registered_at
           OR (candidate->>'first_seen_at')::timestamptz IS DISTINCT FROM capture.first_seen_at
           OR capture.first_seen_at>capture.registered_at OR capture.registered_at>seal_time
           OR (capture.source_id,capture.surface,capture.request_key,capture.blob_sha256)
              IS DISTINCT FROM (binding.source_id,binding.surface,binding.request_key,binding.expected_input_sha256)
           OR NOT EXISTS(SELECT 1 FROM eqos.retained_intake_witness_attempts link
                JOIN eqos.acquisition_attempts a ON a.id=link.attempt_id
                WHERE link.witness_id=header.id AND link.binding_id=binding.id
                    AND a.capture_ref_id=capture.id) THEN
            RAISE EXCEPTION 'retained intake capture physical identity/payload/clock differs'
                USING ERRCODE='23514';
        END IF;
        SELECT count(*) INTO row_count FROM eqos.retained_intake_witness_attempts link
            JOIN eqos.acquisition_attempts a ON a.id=link.attempt_id
            WHERE link.witness_id=header.id AND link.binding_id=binding.id AND a.capture_ref_id=capture.id
                AND a.stage='EXTRACTION' AND a.package_id IS NULL AND a.statement_family IS NULL;
        IF row_count<>1 OR NOT EXISTS(SELECT 1 FROM eqos.retained_intake_witness_captures link
            JOIN eqos.retained_intake_witness_attempts al ON al.witness_id=link.witness_id AND al.binding_id=link.binding_id
            JOIN eqos.acquisition_attempts a ON a.id=al.attempt_id AND a.capture_ref_id=link.capture_ref_id
            WHERE link.witness_id=header.id AND link.capture_ref_id=capture.id
                AND a.stage='EXTRACTION' AND a.package_id IS NULL AND a.statement_family IS NULL
                AND (a.outcome='COMPLETE')=(link.disposition='PACKAGE_MEMBER')
                AND (link.disposition='PACKAGE_MEMBER')=EXISTS(SELECT 1 FROM eqos.package_members m
                    WHERE m.package_id=header.package_id AND m.capture_ref_id=capture.id
                        AND m.representation=binding.representation AND m.knowledge_time=binding.knowledge_time
                        AND m.knowledge_time_raw=binding.filed_at_raw AND m.knowledge_time_status='KNOWN')) THEN
            RAISE EXCEPTION 'retained intake captured disposition/overall extraction differs'
                USING ERRCODE='23514';
        END IF;
    END LOOP;
    IF EXISTS(SELECT 1 FROM eqos.package_members m WHERE m.package_id=header.package_id
        AND NOT EXISTS(SELECT 1 FROM eqos.retained_intake_witness_captures c
            WHERE c.witness_id=header.id AND c.capture_ref_id=m.capture_ref_id AND c.disposition='PACKAGE_MEMBER'))
       OR jsonb_array_length(generation->'members')<>(SELECT count(*) FROM eqos.package_members WHERE package_id=header.package_id)
       OR (SELECT jsonb_agg((item->>'capture_ref_id')::bigint ORDER BY (item->>'capture_ref_id')::bigint)
            FROM jsonb_array_elements(generation->'members') AS members(item)) IS DISTINCT FROM
          (SELECT jsonb_agg(capture_ref_id ORDER BY capture_ref_id)
            FROM eqos.package_members WHERE package_id=header.package_id)
       OR EXISTS(SELECT 1 FROM jsonb_array_elements(generation->'members') AS members(item)
            WHERE NOT EXISTS(SELECT 1 FROM eqos.package_members m WHERE m.package_id=header.package_id
                AND m.capture_ref_id=(item->>'capture_ref_id')::bigint AND m.representation=item->>'representation'))
       OR EXISTS(SELECT 1 FROM jsonb_array_elements(generation->'members') AS members(item)
            JOIN eqos.capture_refs c ON c.id=(item->>'capture_ref_id')::bigint
            JOIN eqos.retained_intake_witness_captures link ON link.witness_id=header.id AND link.capture_ref_id=c.id
            JOIN eqos.retained_intake_witness_bindings b ON b.id=link.binding_id
            WHERE item->>'source_id' IS DISTINCT FROM c.source_id
                OR item->>'surface' IS DISTINCT FROM c.surface
                OR item->>'blob_sha256' IS DISTINCT FROM c.blob_sha256
                OR item->>'record_sha256' IS DISTINCT FROM c.record_sha256
                OR (item->>'capture_registered_at')::timestamptz IS DISTINCT FROM c.registered_at
                OR (item->>'capture_first_seen_at')::timestamptz IS DISTINCT FROM c.first_seen_at
                OR item->'extractor_pin' IS DISTINCT FROM jsonb_build_object(
                    'version',b.extractor_version,'content_sha256',b.extractor_sha256)) THEN
        RAISE EXCEPTION 'retained intake successful package-member closure differs' USING ERRCODE='23514';
    END IF;
    SELECT count(*),jsonb_agg(artifact ORDER BY artifact COLLATE "C") INTO total,expected
        FROM eqos.retained_intake_witness_pins WHERE witness_id=header.id;
    IF total<>NEW.pin_count OR total<>jsonb_array_length(header.canonical_payload->'pins')
       OR total<>7+jsonb_array_length(generation->'extractor_pins')
       OR expected IS DISTINCT FROM (SELECT jsonb_agg(item->'artifact' ORDER BY ordinal)
            FROM jsonb_array_elements(header.canonical_payload->'pins')
                WITH ORDINALITY AS rows(item,ordinal)) THEN
        RAISE EXCEPTION 'retained intake complete pin counts differ' USING ERRCODE='23514';
    END IF;
    FOR candidate IN SELECT item FROM jsonb_array_elements(header.canonical_payload->'pins') AS rows(item) LOOP
        SELECT p.* INTO pin FROM eqos.retained_intake_witness_pins link
            JOIN eqos.version_pins p ON p.id=link.version_pin_id
            WHERE link.witness_id=header.id AND link.artifact=candidate->>'artifact'
                AND link.artifact=p.artifact AND link.version_pin_id=(candidate->>'id')::bigint;
        IF NOT FOUND OR candidate-'pinned_at' IS DISTINCT FROM to_jsonb(pin)-'pinned_at'
           OR (candidate->>'pinned_at')::timestamptz IS DISTINCT FROM pin.pinned_at OR pin.pinned_at>seal_time THEN
            RAISE EXCEPTION 'retained intake version pin payload/clock differs' USING ERRCODE='23514';
        END IF;
        IF pin.artifact='vendor_publication' THEN
            expected:=jsonb_build_object('version',header.publication_version,'content_sha256',header.publication_sha256);
        ELSIF pin.artifact IN ('dictionary','formula_set','mapping_set','normalisation_policy','alignment_rules','source_authority') THEN
            expected:=generation->(pin.artifact||'_pin');
        ELSE
            SELECT item-'representation' INTO expected FROM jsonb_array_elements(generation->'extractor_pins') AS extractors(item)
                WHERE 'extractor_'||lower(item->>'representation')=pin.artifact;
        END IF;
        IF expected IS DISTINCT FROM jsonb_build_object('version',pin.version,'content_sha256',pin.content_sha256) THEN
            RAISE EXCEPTION 'retained intake generation pin differs' USING ERRCODE='23514';
        END IF;
    END LOOP;
    IF EXISTS(SELECT 1 FROM eqos.retained_intake_witness_bindings b WHERE b.witness_id=header.id
        AND NOT EXISTS(SELECT 1 FROM eqos.retained_intake_witness_pins link
            JOIN eqos.version_pins p ON p.id=link.version_pin_id
            WHERE link.witness_id=header.id AND link.artifact='extractor_'||lower(b.representation)
                AND p.version=b.extractor_version AND p.content_sha256=b.extractor_sha256)) THEN
        RAISE EXCEPTION 'retained intake binding extractor pin differs' USING ERRCODE='23514';
    END IF;
    SELECT encode(sha256(convert_to(coalesce(string_agg(line,'' ORDER BY line COLLATE "C"),''),'UTF8')),'hex')
    INTO closure FROM (
        SELECT 'B'||chr(9)||representation||chr(10) AS line
            FROM eqos.retained_intake_witness_bindings WHERE witness_id=header.id
        UNION ALL SELECT 'A'||chr(9)||b.representation||chr(9)||a.attempt_id::text||chr(10)
            FROM eqos.retained_intake_witness_attempts a JOIN eqos.retained_intake_witness_bindings b ON b.id=a.binding_id
            WHERE a.witness_id=header.id
        UNION ALL SELECT 'C'||chr(9)||b.representation||chr(9)||c.capture_ref_id::text||chr(9)||c.disposition||chr(10)
            FROM eqos.retained_intake_witness_captures c JOIN eqos.retained_intake_witness_bindings b ON b.id=c.binding_id
            WHERE c.witness_id=header.id
        UNION ALL SELECT 'P'||chr(9)||artifact||chr(9)||version_pin_id::text||chr(10)
            FROM eqos.retained_intake_witness_pins WHERE witness_id=header.id
    ) AS lines;
    IF NEW.closure_sha256 IS DISTINCT FROM closure THEN
        RAISE EXCEPTION 'retained intake canonical closure digest differs' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER guard_retained_intake_header BEFORE INSERT ON eqos.retained_intake_witnesses
FOR EACH ROW EXECUTE FUNCTION eqos.guard_retained_intake_header();
CREATE TRIGGER guard_retained_intake_seal BEFORE INSERT ON eqos.retained_intake_witness_seals
FOR EACH ROW EXECUTE FUNCTION eqos.guard_retained_intake_seal();

DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['retained_intake_witnesses','retained_intake_witness_bindings',
        'retained_intake_witness_attempts','retained_intake_witness_captures',
        'retained_intake_witness_pins','retained_intake_witness_seals'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()',table_name);
        EXECUTE format('CREATE TRIGGER guard_retained_intake_statement BEFORE INSERT ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.guard_retained_intake_statement()',table_name);
        EXECUTE format('REVOKE ALL ON TABLE eqos.%I FROM PUBLIC,eqos_runtime',table_name);
        EXECUTE format('GRANT SELECT,INSERT ON TABLE eqos.%I TO eqos_runtime',table_name);
        EXECUTE format('REVOKE ALL ON SEQUENCE eqos.%I FROM PUBLIC,eqos_runtime',table_name||'_id_seq');
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_runtime',table_name||'_id_seq');
        IF table_name NOT IN ('retained_intake_witnesses','retained_intake_witness_seals') THEN
            EXECUTE format('CREATE TRIGGER guard_retained_intake_child BEFORE INSERT ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.guard_retained_intake_child()',table_name);
        END IF;
    END LOOP;
END $$;

REVOKE ALL ON FUNCTION eqos.retained_intake_safe_label(text),eqos.retained_intake_json(jsonb),
    eqos.retained_intake_hash(jsonb),eqos.retained_intake_iso_utc(timestamptz),
    eqos.retained_intake_filed_at(text),eqos.require_retained_intake_read_committed(),
    eqos.lock_unsealed_retained_intake(bigint),eqos.guard_retained_intake_evidence_input(),
    eqos.guard_retained_intake_statement(),
    eqos.guard_retained_intake_header(),eqos.guard_retained_intake_child(),
    eqos.guard_retained_intake_seal() FROM PUBLIC,eqos_runtime;
GRANT EXECUTE ON FUNCTION eqos.retained_intake_safe_label(text),eqos.retained_intake_json(jsonb),
    eqos.retained_intake_hash(jsonb),eqos.retained_intake_filed_at(text) TO eqos_runtime;
