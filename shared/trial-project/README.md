# Curated trial archive v1

`manifest.json` and the original JPEG copies in `photos/` form the complete archive.
Source images are the existing public application demo assets `web/public/demo/Screenshot_23.jpg`
and `Screenshot_89.jpg`; no held-out datasets are included. Labels, observations, boxes,
outcomes and signals are hand-authored teaching examples, not verified model inference.

Schema version 1 has exact top-level fields: `schema_version`, `name`, `description`,
`plan`, `examples`, `files`. The application validator defines strict nested fields,
limits, timezone-aware date ordering, normalized boxes and exact JPEG SHA256 hashes.
Archives contain only `manifest.json` and listed `photos/*.jpg`, and are read in memory,
never extracted or executed. ZIP duplicates, traversal, symlinks, encrypted entries,
extra files, malformed schemas, oversized payloads and invalid images are rejected.

Import requires authentication, same-origin requests and UUID Idempotency-Key. Keys
are scoped to the importing user; retries return the same project, different content
conflicts. A new project, owner membership, zone and native editable plan revision are
created atomically. Imported photos receive fresh IDs. Example results, annotations
and signals remain in a separate illustrative manifest, avoiding forged immutable
analysis evidence. `GET /projects/{id}/trial` exposes all example content and authorized
photo URLs. Fetch those JPEG bytes for the ordinary upload/analysis flow with its normal
explicit cloud consent. A real rerun creates ordinary independent analysis evidence.

Public fixture APIs: `/trial/project.zip`, `/trial/photos.zip`, `/trial/preview`,
`/trial/photos/{filename}`. Private imported APIs enforce current membership on each
request. Download responses never include private project content.

Assistant configuration uses existing DEEPSEEK_API_KEY (direct Responses API) or
YANDEX_AI_STUDIO_API_KEY plus YANDEX_CLOUD_FOLDER_ID. It sends only the authorized
project's bounded current plan, signals and saved normalized results, never credentials
or raw provider responses. Without a working provider, responses explicitly disclose
unavailability and offer deterministic product help. Project conversations are private
to user+project and expire after 30 days; general help is not persisted.

Each example also includes nonempty `corrections`: records with exact fields `photo`,
`original_annotations`, `corrected_annotations`, `comment`. Both annotation arrays use
`{label, box:[left,top,right,bottom]}` with bounded normalized ordered boxes. Corrections
must differ, retain a nonempty comment, and reference a photo belonging to that example.
Both source and corrected teaching annotations are preserved separately; neither is
machine evidence. Preview APIs remap correction `photo` to the same authorized/public
photo URL and add `illustrative:true` for display.
