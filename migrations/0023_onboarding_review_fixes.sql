-- D6 pre-freeze review fixes (plan D6 D3.1). 0001--0022 are immutable.

-- A non-VERIFIED unit must say why: the 0022 CHECK passed a NULL reason (NULL is not false).
ALTER TABLE eqos.namespace_verifications DROP CONSTRAINT namespace_verifications_check;
ALTER TABLE eqos.namespace_verifications ADD CHECK (
    state = 'VERIFIED' OR (reason IS NOT NULL AND char_length(reason) > 0));
