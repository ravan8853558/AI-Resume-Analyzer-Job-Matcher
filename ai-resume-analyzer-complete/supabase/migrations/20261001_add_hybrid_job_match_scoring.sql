-- Hybrid semantic + deterministic job matching
alter table public.job_matches
  add column if not exists skill_match_score numeric,
  add column if not exists semantic_score numeric,
  add column if not exists scoring_version text not null default 'hybrid-v1';

create or replace function public.match_single_job_by_embedding(
  query_embedding extensions.vector(1536),
  target_job_id uuid
)
returns double precision
language sql
stable
security invoker
set search_path = public, extensions
as $$
  select 1 - (j.embedding <=> query_embedding) as similarity
  from public.jobs j
  where j.id = target_job_id
    and j.user_id = (select auth.uid())
    and j.embedding is not null;
$$;

revoke all on function public.match_single_job_by_embedding(extensions.vector(1536), uuid) from public;
grant execute on function public.match_single_job_by_embedding(extensions.vector(1536), uuid) to authenticated;
