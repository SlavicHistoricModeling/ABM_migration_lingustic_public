# Manual Zenodo Upload Instructions

This replication package is ready for deposit. Zenodo requires authentication, so the upload step is performed manually by the depositor. Follow the steps below to publish the deposit.

## 1. Prepare the upload archive

From the deposit folder (the contents of this repository at the tagged release commit), produce a single archive:

```bash
# Linux / macOS:
cd ..
tar czf ABM_migration_lingustic_public_v1.0.0.tar.gz ABM_migration_lingustic_public/

# Or as a zip (Windows users):
# Right-click the folder in Explorer → "Send to" → "Compressed (zipped) folder"
```

Either format is acceptable to Zenodo. Keep the archive size under Zenodo's per-file limit (currently 50 GB free tier).

Alternatively, Zenodo's GitHub integration can auto-publish a release; see step 4 below.

## 2. Log in and start a new upload

1. Go to <https://zenodo.org> and log in (or create an account; institutional ORCID login is recommended).
2. Click "New upload" at the top.
3. **Upload type:** select "Software" (the deposit contains executable code; "Dataset" is the alternative for data-only deposits — Software fits better here given the engine code).
4. Drag-and-drop the archive (or upload the unpacked folder; Zenodo accepts both).

## 3. Fill the metadata

| Field | Value |
|---|---|
| Title | Demographic-Spatial Modeling of Slavic Linguistic Expansion in the Balkans: Replication Package for the JLG Submission |
| Creators | [author redacted for double-blind review] (add ORCID and affiliation if applicable; both are placeholders in `CITATION.cff` and should be filled before submission) |
| Description | Paste the **Overview** section of `README.md` (approximately 3 paragraphs) |
| Keywords | agent-based modeling; Slavic; Balkan; demographic simulation; language shift; substrate continuity; historical linguistics |
| License | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Publication date | 2026-05-27 (or the actual publication date if different) |
| Version | v1.0.0 |
| Language | English |

**Related identifiers:**

- Link to this GitHub repository: `https://github.com/stoleskopje/ABM_migration_lingustic_public` (relation: "is supplement to")
- Permanent identifiers for the companion submissions (under review at separate journals) should be added once those submissions reach decision. See the "Related work" section of `README.md` for the current status of each companion.

## 4. Reserve a DOI before publishing

Zenodo offers a "Pre-reserve DOI" toggle. Enable it before publishing — this lets you cite the DOI in the JLG paper before the deposit is publicly visible.

## 5. Publish

Click "Publish" once metadata is complete. Zenodo will mint the DOI and the deposit becomes publicly accessible immediately.

**After publishing:**

1. Record the assigned DOI.
2. Update the JLG paper's references with the DOI.
3. Update this replication package's `CITATION.cff` and `README.md` with the DOI (in a follow-up commit; Zenodo will assign a new version DOI for the update if you re-deposit, but for a metadata-only fix the original DOI can stay).
4. Update `docs/CHANGES_jlg.md` with a follow-up entry recording the assigned DOI.

## Optional: GitHub-integrated auto-publish

Zenodo can auto-publish a tagged release from this GitHub repository:

1. On Zenodo, go to your account settings → GitHub integration → enable for `stoleskopje/ABM_migration_lingustic_public`.
2. Create a GitHub release: `git tag v1.0.0 && git push --tags` then create a release in the GitHub web interface from the v1.0.0 tag.
3. Zenodo automatically archives the release and mints a DOI. The metadata is read from `CITATION.cff` (which is already in this repository's root).

The auto-publish path is preferred for ongoing version management because each new GitHub release automatically produces a new Zenodo DOI in the same concept-DOI lineage.
