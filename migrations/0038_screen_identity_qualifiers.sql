-- D7 screen-export phase review r1 #5, #9. 0001--0037 are immutable.
-- A bound Tijori member records whether its slug is a VERIFIED Tijori slug of the ISIN's entity
-- (null for every other member): binding without one is registry membership, never vendor
-- identity verification. A Tijori overview read keeps the identifiers it was gated on, so its
-- review replays that gate whatever the watchlist says later; rows before this migration have
-- neither.

ALTER TABLE eqos.screen_members ADD COLUMN slug_verified boolean,
    ADD CHECK (slug_verified IS NULL OR listing_id IS NOT NULL);

ALTER TABLE eqos.screen_other_vendor_reads ADD COLUMN tijori_slug text,
    ADD COLUMN tijori_company_id bigint,
    ADD CHECK ((tijori_slug IS NULL) = (tijori_company_id IS NULL)),
    ADD CHECK (tijori_slug IS NULL OR capture_ref_id IS NOT NULL);
