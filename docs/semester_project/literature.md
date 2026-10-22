# Literature (public sources only)

Reference list for the implementation side. Full texts of these and any non-public reports
live in `docs/semester_project/private/` (local only, git-ignored).

| Key | Reference | Link | Why it matters here |
|---|---|---|---|
| Hansson2026 | Hansson J., Humbert G., Koirala B. *A techno-economic analysis of the integration of edge data centres into tertiary buildings.* Preprint, SSRN, not peer reviewed. | https://ssrn.com/abstract=7321983 | Source of the baseline model: `examples/1_WH` (WHR scenario) and `examples/4_WH+PV+DHN+Flex` (full scenario). DC and hybrid-cooling model (Eqs. 4–7), IT flexibility (Eq. 9, β = 0.1). |
| HEATWISE-D7.2 | Humbert G., Hansson J., Koirala B. P. *Techno-economic analysis of cooling technologies for edge data centres integrated into tertiary buildings.* HEATWISE Deliverable D7.2, Empa, Dec 2025 (dissemination: public). | www.heatwise.eu | Same ehubX model family. Air vs liquid cooling cases, AWHP COP pre-processing, NEST three-network setup (LT 7/14, MT 35/25, HT 65/45 °C). |
| Ravi2026 | Ravi S. S., Löffler T. S., Pina E. A., Sharma S., Lepour D., Terrier C., Maréchal F. *From servers to services: modeling data centers as heat-active urban energy prosumers.* Applied Energy 402 (2026) 127049. | https://doi.org/10.1016/j.apenergy.2025.127049 | Campus-scale DC prosumer model (EPFL). Flexible workloads, legacy vs exergy-aware heat recovery. Positioning reference for the RQ. |
