# LinkedIn Match-Based Easy Apply Workflow

## Purpose
Scan a LinkedIn job collection (e.g. "Recommended"), evaluate each posting against
a numeric fit threshold using LinkedIn's own "Show match details" feature, and
apply automatically only to postings that clear the bar — while pausing for
human input on anything involving sensitive personal/financial data or
subjective fit judgment.

## Required human-in-the-loop checkpoints (do not automate away)
1. Any field requesting current/expected CTC (fixed or variable), RSU/equity value,
   nationality, or citizenship — an agent must stop and ask the human, never guess.
2. Any additional-questions field asking for years of experience in a specific
   discipline that is not clearly stated in the candidate's resume.
3. Any judgment call on whether a role is a reasonable domain fit despite a high
   numeric match score (numeric match % does not capture domain mismatch).
4. The initial go-ahead to start submitting applications, and periodic check-ins
   reporting tallies back to the human.
Running this unattended past these checkpoints is out of scope for this document,
both because it risks LinkedIn account restriction (automated use violates
LinkedIn's User Agreement) and because sensitive-data decisions shouldn't be made
by a script.

## Prerequisites
- Logged-in LinkedIn session in the browser.
- A resume file already uploaded under
  Settings → Data privacy → Job application settings → "Resumes and application data".
  Note its exact filename (e.g. `RAHUL_GOEL_Resume_Final.pdf`) to confirm it's
  selected during each application.
- Baseline profile facts already known and reusable across applications: notice
  period, willingness to relocate, work-authorization status, preferred
  cities. These get reused verbatim in additional-questions screens instead of
  being re-derived each time.
- An agreed match-score threshold (this run used ≥80%) and a defined scope
  (this run used the first ~50–100 postings in relevance order, since scanning
  every result in an 800+ result collection isn't practical).

## Definitions
- **Match score** = (qualifications matched) ÷ (qualifications required), read
  directly from LinkedIn's "Show match details" panel line: "Matches X of Y
  required qualifications." The separate "additional qualifications" count is
  noted but not included in the score.
- **Easy Apply job**: application is submitted entirely within LinkedIn's modal
  flow.
- **External-apply job**: job header shows "Responses managed off LinkedIn" —
  clicking Apply leaves LinkedIn for a third-party site. These are always
  skipped/flagged, never auto-submitted, regardless of match score.

## Per-job procedure
1. Open the job posting (from the collection list or by direct
   `https://www.linkedin.com/jobs/view/{jobId}` URL).
2. Check the header for "Responses managed off LinkedIn."
   - If present: log the job as **external-apply, flagged**, and move to the
     next posting. Do not click into the external application.
3. If Easy Apply is present, click "Show match details," wait ~2 seconds for
   the panel to render, and read "Matches X of Y required qualifications."
4. Compute match score = X ÷ Y.
   - If score < threshold (80%): log as **skipped, below threshold**, move on.
   - If score ≥ threshold: continue to step 5.
5. Click "Easy Apply" to open the application modal.
6. **Contact info screen**: verify name, email, and phone are correctly
   pre-filled. If a city/location field is required and empty, type the
   city name, wait for the autocomplete dropdown, and click the matching
   suggestion (never press Enter — on LinkedIn this can discard the
   selection rather than confirm it). Click Next.
   - Sanity-check the email field specifically after any click near it;
     misclicks can silently swap it to a different saved address.
7. **Resume screen**: confirm the intended resume file is selected (should
   show a checkmark/selected state). Click Next.
8. **"Mark as top choice" screen** (if shown, Premium feature): leave
   unchecked unless the human has said otherwise. Click Next.
9. **Additional questions screen(s)**: for each question —
   - If it matches a known baseline fact (notice period, relocation,
     work authorization, a skill/experience number clearly stated in the
     resume), fill it in directly.
   - If it asks for CTC, RSU, nationality, citizenship, or an experience
     number not supported by the resume, **stop**: do not submit, click
     the close/X control, and choose "Save" (not "Discard") so the draft
     is preserved. Log the job as **paused, needs human input**, listing
     exactly which fields are blocking it. Move to the next posting.
   - Exception: if the role is also a poor domain fit on its face (not
     just missing data), it's reasonable to Discard rather than Save,
     since completing it later isn't worthwhile either way — but this is
     a judgment call to flag to the human, not a default.
10. **Review screen**: scroll through and confirm all shown answers are
    correct.
11. Click **Submit application**.
12. Confirm success via LinkedIn's "Your application was sent to
    [Company]!" confirmation.
13. Dismiss any "update your profile" upsell prompt ("Not now").
14. Log the job as **submitted**, with company, title, location, and match
    score, then proceed to the next posting.

## De-duplication
Before applying, check whether the same company + title combination has
already been submitted earlier in the run (LinkedIn sometimes lists the same
opening twice, e.g. two locations for one role). Skip and log as **duplicate**
rather than re-applying.

## Tally / reporting format
Maintain a running log with four buckets, each with company, title, location,
and (where applicable) match score or blocking reason:
- Submitted
- Paused / saved as draft (needs human input, with the specific missing
  fields named)
- Skipped — below threshold
- Skipped/flagged — external-apply only

Report this tally back to the human periodically and at the end of each
scanning session, and explicitly ask before continuing further into the
collection or before resuming any paused drafts.

## Known pitfalls
- Pressing Enter in an autocomplete field can silently fail to apply the
  selection — always click the dropdown suggestion.
- Take a screenshot after any click near a pre-filled contact field to
  confirm it wasn't accidentally changed.
- Large collections (800+ results) make "scan everything" impractical —
  agree scope with the human up front rather than assuming full coverage.
- Some postings require additional questions beyond a single screen —
  don't submit until every required field on every screen is either
  answered from verified facts or explicitly paused on.
