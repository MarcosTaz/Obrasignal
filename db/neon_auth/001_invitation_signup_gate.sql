-- ObraSignal only. Applied to royal-cloud-69492271 / obrasignal_auth on 2026-10-15.
-- IMPORTANT: run only against a dedicated ObraSignal Neon Auth branch.
-- Name protocol for Better Auth email signup: OS-<48 hex>|<display-name>.
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
CREATE TABLE IF NOT EXISTS public.obrasignal_auth_invites (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 email text NOT NULL,
 token_hash bytea NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 used_at timestamptz,
 revoked_at timestamptz,
 created_by text NOT NULL,
 CONSTRAINT obrasignal_inv_email CHECK (email=lower(btrim(email)) AND length(email) BETWEEN 6 AND 254),
 CONSTRAINT obrasignal_inv_expiry CHECK (expires_at>created_at)
);
CREATE INDEX IF NOT EXISTS obrasignal_auth_invites_email_idx ON public.obrasignal_auth_invites(email,expires_at DESC);
ALTER TABLE public.obrasignal_auth_invites ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.obrasignal_auth_invites FROM PUBLIC;
CREATE OR REPLACE FUNCTION public.obrasignal_validate_invited_signup()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $body$
DECLARE v_code text; v_name text; v_count integer;
BEGIN
 IF NEW.email IS NULL OR lower(btrim(NEW.email)) <> NEW.email OR NEW.name IS NULL OR NEW.name !~ '^OS-[0-9a-f]{48}\|' THEN
  RAISE EXCEPTION 'invitation_required' USING ERRCODE='42501';
 END IF;
 v_code:=split_part(NEW.name,'|',1);
 v_name:=substr(NEW.name,length(v_code)+2);
 IF length(btrim(v_name))<1 OR length(v_name)>160 THEN RAISE EXCEPTION 'invalid_display_name' USING ERRCODE='22023'; END IF;
 UPDATE public.obrasignal_auth_invites SET used_at=now()
 WHERE email=NEW.email AND token_hash=public.digest(convert_to(v_code,'UTF8'),'sha256')
 AND used_at IS NULL AND revoked_at IS NULL AND expires_at>now();
 GET DIAGNOSTICS v_count=ROW_COUNT;
 IF v_count<>1 THEN RAISE EXCEPTION 'invalid_or_expired_invitation' USING ERRCODE='42501'; END IF;
 NEW.name:=btrim(v_name);
 RETURN NEW;
END $body$;
REVOKE ALL ON FUNCTION public.obrasignal_validate_invited_signup() FROM PUBLIC;
DO $guard$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='obrasignal_invite_signup_gate' AND tgrelid='neon_auth."user"'::regclass) THEN
  CREATE TRIGGER obrasignal_invite_signup_gate BEFORE INSERT ON neon_auth."user"
  FOR EACH ROW EXECUTE FUNCTION public.obrasignal_validate_invited_signup();
 END IF;
END $guard$;
-- Issuance must be invoked ONLY using the isolated privileged DB owner connection.
CREATE OR REPLACE FUNCTION public.obrasignal_issue_auth_invite(p_email text,p_created_by text,p_hours integer DEFAULT 72)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $body$
DECLARE e text:=lower(btrim(coalesce(p_email,''))); token text; v_id uuid; expires timestamptz;
BEGIN
 IF e !~ '^[a-z0-9_+.%!-]+@[a-z0-9.-]+\.[a-z]{2,}$' OR length(e)>254 THEN RAISE EXCEPTION 'invalid_email' USING ERRCODE='22023'; END IF;
 IF p_created_by IS NULL OR length(btrim(p_created_by)) NOT BETWEEN 1 AND 128 THEN RAISE EXCEPTION 'invalid_issuer' USING ERRCODE='22023'; END IF;
 IF p_hours IS NULL OR p_hours NOT BETWEEN 1 AND 168 THEN RAISE EXCEPTION 'invalid_ttl' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM neon_auth."user" WHERE lower(email)=e) THEN RAISE EXCEPTION 'already_registered' USING ERRCODE='22023'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(e,0));
 UPDATE public.obrasignal_auth_invites SET revoked_at=now() WHERE email=e AND used_at IS NULL AND revoked_at IS NULL;
 token:='OS-'||encode(public.gen_random_bytes(24),'hex');
 expires:=now()+make_interval(hours=>p_hours);
 INSERT INTO public.obrasignal_auth_invites(email,token_hash,created_by,expires_at)
 VALUES(e,public.digest(convert_to(token,'UTF8'),'sha256'),p_created_by,expires) RETURNING id INTO v_id;
 RETURN jsonb_build_object('id',v_id,'email',e,'code',token,'expires_at',expires);
END $body$;
REVOKE ALL ON FUNCTION public.obrasignal_issue_auth_invite(text,text,integer) FROM PUBLIC;
