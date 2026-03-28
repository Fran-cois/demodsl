# Performance Results

**Date**: 2026-03-28T15:14:16.085623+00:00  
**Python**: 3.11.9  
**DemoDSL**: 2.0.0  
**Venv**: `/Users/famat/PycharmProjects/SIDE/demodsl/.venv-perf`  
**Executable**: `/Users/famat/PycharmProjects/SIDE/demodsl/.venv-perf/bin/python`  
**Baseline**: 2026-03-28T14:43:04.463069+00:00  
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
| 🟢 | build_narration_texts | 0.0004 | -66.7% | 0.0005 | -61.5% | 0.0003 | 100 |
| 🟢 | build_pipeline_chain | 0.0023 | -79.8% | 0.0025 | -79.5% | 0.0023 | 200 |
| 🟢 | click | 0.0042 | -54.3% | 0.0039 | -57.1% | 0.0030 | 500 |
| 🟢 | click_describe | 0.0002 | -66.7% | 0.0002 | -71.4% | 0.0002 | 500 |
| 🟢 | collect_post_effects | 0.0018 | -62.5% | 0.0016 | -40.7% | 0.0012 | 100 |
| 🟢 | dispatch_click | 0.0008 | -69.2% | 0.0009 | -67.9% | 0.0008 | 500 |
| 🟢 | dispatch_navigate | 0.0008 | -70.4% | 0.0009 | -66.7% | 0.0008 | 500 |
| 🟢 | dispatch_screenshot | 0.0017 | -63.8% | 0.0034 | -40.4% | 0.0014 | 500 |
| 🟢 | dispatch_scroll | 0.0009 | -66.7% | 0.0017 | -39.3% | 0.0008 | 500 |
| 🟢 | dispatch_type | 0.0008 | -69.2% | 0.0009 | -66.7% | 0.0008 | 500 |
| 🟢 | dispatch_wait_for | 0.0012 | -55.6% | 0.0019 | -40.6% | 0.0008 | 500 |
| 🟢 | dry_run_narrations | 0.0007 | -69.6% | 0.0008 | -65.2% | 0.0006 | 100 |
| 🟢 | engine_init | 0.6253 | -69.6% | 0.6577 | -71.5% | 0.6241 | 100 |
| 🟢 | engine_validate | 0.0002 | -77.8% | 0.0003 | -70.0% | 0.0002 | 100 |
| 🟢 | measure_durations_empty | 0.0001 | -83.3% | 0.0002 | -66.7% | 0.0001 | 100 |
| 🟢 | navigate | 0.0043 | -66.9% | 0.0051 | -81.3% | 0.0036 | 500 |
| 🟢 | navigate_describe | 0.0001 | -80.0% | 0.0002 | -60.0% | 0.0001 | 500 |
| 🟢 | parse_effect | 0.0026 | -62.3% | 0.0032 | -62.4% | 0.0025 | 200 |
| 🟢 | parse_full_config | 0.0114 | -45.2% | 0.0122 | -41.6% | 0.0107 | 200 |
| 🟢 | parse_locator | 0.0005 | -37.5% | 0.0005 | -37.5% | 0.0005 | 200 |
| 🟢 | parse_minimal_config | 0.0028 | -28.2% | 0.0029 | -32.6% | 0.0027 | 200 |
| 🟢 | parse_step_click | 0.0012 | -40.0% | 0.0013 | -43.5% | 0.0012 | 200 |
| 🟢 | parse_step_navigate | 0.0009 | -40.0% | 0.0010 | -37.5% | 0.0008 | 200 |
| 🟢 | parse_step_screenshot | 0.0008 | -42.9% | 0.0008 | -46.7% | 0.0007 | 200 |
| 🟢 | parse_step_scroll | 0.0009 | -40.0% | 0.0009 | -43.8% | 0.0009 | 200 |
| 🟢 | parse_step_type | 0.0012 | -40.0% | 0.0013 | -38.1% | 0.0012 | 200 |
| 🟢 | parse_step_wait_for | 0.0011 | -42.1% | 0.0012 | -40.0% | 0.0011 | 200 |
| 🟢 | parse_step_with_effects | 0.0083 | -59.5% | 0.0084 | -61.6% | 0.0081 | 200 |
| 🟢 | registry_init_register | 0.0045 | -80.9% | 0.0046 | -83.7% | 0.0044 | 200 |
| 🟢 | registry_lookup_browser | 0.0015 | -84.7% | 0.0018 | -82.2% | 0.0015 | 200 |
| 🟢 | registry_lookup_post | 0.0013 | -85.7% | 0.0017 | -81.7% | 0.0012 | 200 |
| 🟢 | scenario_dry_run | 0.0051 | -69.1% | 0.0056 | -67.1% | 0.0047 | 100 |
| 🟢 | scenario_orch_init | 0.0002 | -66.7% | 0.0002 | -71.4% | 0.0002 | 100 |
| 🟢 | screenshot | 0.0053 | -53.1% | 0.0058 | -52.5% | 0.0038 | 500 |
| 🟢 | screenshot_describe | 0.0003 | -40.0% | 0.0003 | -50.0% | 0.0003 | 500 |
| 🟢 | scroll | 0.0048 | -44.8% | 0.0092 | -8.0% | 0.0036 | 500 |
| 🟢 | scroll_describe | 0.0002 | -66.7% | 0.0002 | -71.4% | 0.0002 | 500 |
| 🟢 | type | 0.0051 | -42.0% | 0.0090 | -2.2% | 0.0031 | 500 |
| 🟢 | type_describe | 0.0002 | -71.4% | 0.0003 | -62.5% | 0.0002 | 500 |
| 🟢 | wait_for | 0.0043 | -51.1% | 0.0043 | -52.7% | 0.0031 | 500 |
| 🟢 | wait_for_describe | 0.0003 | -62.5% | 0.0003 | -62.5% | 0.0003 | 500 |
| 🟢 | yaml_load_and_parse | 1.0751 | -70.4% | 1.1558 | -71.2% | 1.0774 | 100 |

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
