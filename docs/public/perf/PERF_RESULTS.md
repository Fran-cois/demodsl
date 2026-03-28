# Performance Results

**Date**: 2026-03-28T15:38:54.613481+00:00  
**Python**: 3.11.9  
**DemoDSL**: 2.0.0  
**Venv**: `~/PycharmProjects/SIDE/demodsl/.venv-perf`  
**Executable**: `~/PycharmProjects/SIDE/demodsl/.venv-perf/bin/python`  
**Baseline**: 2026-03-28T15:14:16.085623+00:00  
**Thresholds**: warn > 10%, fail > 25%  

## Hardware

| Field | Value |
|---|---|
| OS | Darwin 25.3.0 |
| Architecture | arm64 |
| CPU | arm (11 logical cores) |
| RAM | 18.0 GB |

## Results

| Status | Action | Mean (ms) | Δ Mean | P95 (ms) | Δ P95 | Median (ms) | Iterations |
|:---:|---|---:|---:|---:|---:|---:|---:|
| 🟢 | build_narration_texts | 0.0004 | +0.0% | 0.0005 | +0.0% | 0.0003 | 100 |
| 🟢 | build_pipeline_chain | 0.0024 | +4.3% | 0.0027 | +8.0% | 0.0023 | 200 |
| 🟢 | click | 0.0042 | +0.0% | 0.0039 | +0.0% | 0.0030 | 500 |
| 🟢 | click_describe | 0.0002 | +0.0% | 0.0002 | +0.0% | 0.0002 | 500 |
| 🟢 | collect_post_effects | 0.0017 | -5.6% | 0.0017 | +6.2% | 0.0012 | 100 |
| 🟢 | dispatch_click | 0.0007 | -12.5% | 0.0008 | -11.1% | 0.0007 | 500 |
| 🟢 | dispatch_navigate | 0.0007 | -12.5% | 0.0008 | -11.1% | 0.0007 | 500 |
| 🟢 | dispatch_screenshot | 0.0013 | -23.5% | 0.0013 | -61.8% | 0.0012 | 500 |
| 🟢 | dispatch_scroll | 0.0008 | -11.1% | 0.0008 | -52.9% | 0.0007 | 500 |
| 🟢 | dispatch_type | 0.0012 | +50.0% | 0.0010 | +11.1% | 0.0008 | 500 |
| 🟢 | dispatch_wait_for | 0.0008 | -33.3% | 0.0008 | -57.9% | 0.0008 | 500 |
| 🟢 | dry_run_narrations | 0.0006 | -14.3% | 0.0007 | -12.5% | 0.0005 | 100 |
| 🟢 | engine_init | 0.6260 | +0.1% | 0.9358 | +42.3% | 0.5837 | 100 |
| 🟢 | engine_validate | 0.0002 | +0.0% | 0.0003 | +0.0% | 0.0002 | 100 |
| 🟢 | measure_durations_empty | 0.0001 | +0.0% | 0.0002 | +0.0% | 0.0001 | 100 |
| 🟢 | navigate | 0.0048 | +11.6% | 0.0058 | +13.7% | 0.0033 | 500 |
| 🟢 | navigate_describe | 0.0001 | +0.0% | 0.0002 | +0.0% | 0.0001 | 500 |
| 🟢 | parse_effect | 0.0023 | -11.5% | 0.0023 | -28.1% | 0.0022 | 200 |
| 🟢 | parse_full_config | 0.0107 | -6.1% | 0.0111 | -9.0% | 0.0104 | 200 |
| 🟢 | parse_locator | 0.0005 | +0.0% | 0.0005 | +0.0% | 0.0005 | 200 |
| 🟢 | parse_minimal_config | 0.0027 | -3.6% | 0.0030 | +3.4% | 0.0027 | 200 |
| 🟢 | parse_step_click | 0.0011 | -8.3% | 0.0012 | -7.7% | 0.0010 | 200 |
| 🟢 | parse_step_navigate | 0.0008 | -11.1% | 0.0008 | -20.0% | 0.0008 | 200 |
| 🟢 | parse_step_screenshot | 0.0008 | +0.0% | 0.0008 | +0.0% | 0.0008 | 200 |
| 🟢 | parse_step_scroll | 0.0008 | -11.1% | 0.0009 | +0.0% | 0.0008 | 200 |
| 🟢 | parse_step_type | 0.0011 | -8.3% | 0.0012 | -7.7% | 0.0011 | 200 |
| 🟢 | parse_step_wait_for | 0.0011 | +0.0% | 0.0012 | +0.0% | 0.0011 | 200 |
| 🟢 | parse_step_with_effects | 0.0101 | +21.7% | 0.0165 | +96.4% | 0.0076 | 200 |
| 🟢 | registry_init_register | 0.0050 | +11.1% | 0.0051 | +10.9% | 0.0050 | 200 |
| 🟢 | registry_lookup_browser | 0.0043 | +186.7% | 0.0137 | +661.1% | 0.0016 | 200 |
| 🟢 | registry_lookup_post | 0.0013 | +0.0% | 0.0013 | -23.5% | 0.0013 | 200 |
| 🟢 | scenario_dry_run | 0.0062 | +21.6% | 0.0067 | +19.6% | 0.0046 | 100 |
| 🟢 | scenario_orch_init | 0.0002 | +0.0% | 0.0002 | +0.0% | 0.0002 | 100 |
| 🟢 | screenshot | 0.0041 | -22.6% | 0.0046 | -20.7% | 0.0033 | 500 |
| 🟢 | screenshot_describe | 0.0001 | -66.7% | 0.0001 | -66.7% | 0.0001 | 500 |
| 🟢 | scroll | 0.0034 | -29.2% | 0.0034 | -63.0% | 0.0030 | 500 |
| 🟢 | scroll_describe | 0.0002 | +0.0% | 0.0002 | +0.0% | 0.0002 | 500 |
| 🟢 | type | 0.0042 | -17.6% | 0.0078 | -13.3% | 0.0028 | 500 |
| 🟢 | type_describe | 0.0002 | +0.0% | 0.0002 | -33.3% | 0.0002 | 500 |
| 🟢 | wait_for | 0.0035 | -18.6% | 0.0039 | -9.3% | 0.0027 | 500 |
| 🟢 | wait_for_describe | 0.0005 | +66.7% | 0.0007 | +133.3% | 0.0003 | 500 |
| 🔴 | yaml_load_and_parse | 1.3497 | +25.5% | 2.1553 | +86.5% | 1.2060 | 100 |

## Regression Summary

No regressions detected. All benchmarks within thresholds. 🟢

## SBOM

<details><summary>47 packages</summary>

- annotated-doc==0.0.4
- annotated-types==0.7.0
- anyio==4.13.0
- certifi==2026.2.25
- click==8.3.1
- coverage==7.13.5
- decorator==5.2.1
- demodsl==2.0.0
- ffmpeg-python==0.2.0
- future==1.0.0
- greenlet==3.3.2
- h11==0.16.0
- httpcore==1.0.9
- httpx==0.28.1
- idna==3.11
- ImageIO==2.37.3
- imageio-ffmpeg==0.6.0
- iniconfig==2.3.0
- markdown-it-py==4.0.0
- mdurl==0.1.2
- moviepy==2.2.1
- numpy==2.4.3
- packaging==26.0
- pillow==11.3.0
- pip==26.0.1
- playwright==1.58.0
- pluggy==1.6.0
- proglog==0.1.12
- psutil==7.2.2
- pydantic==2.12.5
- pydantic_core==2.41.5
- pydub==0.25.1
- pyee==13.0.1
- Pygments==2.19.2
- pytest==9.0.2
- pytest-asyncio==1.3.0
- pytest-cov==7.1.0
- python-dotenv==1.2.2
- PyYAML==6.0.3
- rich==14.3.3
- ruff==0.15.8
- setuptools==65.5.0
- shellingham==1.5.4
- tqdm==4.67.3
- typer==0.24.1
- typing-inspection==0.4.2
- typing_extensions==4.15.0

</details>
