# Performance Results

**Date**: 2026-03-28T15:14:16.085623+00:00  
**Python**: 3.11.9  
**DemoDSL**: 2.0.0  
**Venv**: `/Users/famat/PycharmProjects/SIDE/demodsl/.venv-perf`  
**Executable**: `/Users/famat/PycharmProjects/SIDE/demodsl/.venv-perf/bin/python`  

## Hardware

| Field | Value |
|---|---|
| OS | Darwin 25.3.0 |
| Architecture | arm64 |
| CPU | arm (11 logical cores) |
| RAM | 18.0 GB |

## Results

| Action | Mean (ms) | Median (ms) | P95 (ms) | Min (ms) | Max (ms) | Iterations |
|---|---:|---:|---:|---:|---:|---:|
| build_narration_texts | 0.0004 | 0.0003 | 0.0005 | 0.0003 | 0.0023 | 100 |
| build_pipeline_chain | 0.0023 | 0.0023 | 0.0025 | 0.0022 | 0.0116 | 200 |
| click | 0.0042 | 0.0030 | 0.0039 | 0.0029 | 0.4247 | 500 |
| click_describe | 0.0002 | 0.0002 | 0.0002 | 0.0001 | 0.0015 | 500 |
| collect_post_effects | 0.0018 | 0.0012 | 0.0016 | 0.0011 | 0.0629 | 100 |
| dispatch_click | 0.0008 | 0.0008 | 0.0009 | 0.0007 | 0.0031 | 500 |
| dispatch_navigate | 0.0008 | 0.0008 | 0.0009 | 0.0007 | 0.0042 | 500 |
| dispatch_screenshot | 0.0017 | 0.0014 | 0.0034 | 0.0013 | 0.0325 | 500 |
| dispatch_scroll | 0.0009 | 0.0008 | 0.0017 | 0.0007 | 0.0241 | 500 |
| dispatch_type | 0.0008 | 0.0008 | 0.0009 | 0.0007 | 0.0030 | 500 |
| dispatch_wait_for | 0.0012 | 0.0008 | 0.0019 | 0.0007 | 0.0093 | 500 |
| dry_run_narrations | 0.0007 | 0.0006 | 0.0008 | 0.0005 | 0.0080 | 100 |
| engine_init | 0.6253 | 0.6241 | 0.6577 | 0.5698 | 0.8346 | 100 |
| engine_validate | 0.0002 | 0.0002 | 0.0003 | 0.0002 | 0.0016 | 100 |
| measure_durations_empty | 0.0001 | 0.0001 | 0.0002 | 0.0001 | 0.0008 | 100 |
| navigate | 0.0043 | 0.0036 | 0.0051 | 0.0034 | 0.1178 | 500 |
| navigate_describe | 0.0001 | 0.0001 | 0.0002 | 0.0001 | 0.0010 | 500 |
| parse_effect | 0.0026 | 0.0025 | 0.0032 | 0.0024 | 0.0115 | 200 |
| parse_full_config | 0.0114 | 0.0107 | 0.0122 | 0.0104 | 0.0575 | 200 |
| parse_locator | 0.0005 | 0.0005 | 0.0005 | 0.0005 | 0.0026 | 200 |
| parse_minimal_config | 0.0028 | 0.0027 | 0.0029 | 0.0026 | 0.0117 | 200 |
| parse_step_click | 0.0012 | 0.0012 | 0.0013 | 0.0010 | 0.0078 | 200 |
| parse_step_navigate | 0.0009 | 0.0008 | 0.0010 | 0.0007 | 0.0076 | 200 |
| parse_step_screenshot | 0.0008 | 0.0007 | 0.0008 | 0.0007 | 0.0026 | 200 |
| parse_step_scroll | 0.0009 | 0.0009 | 0.0009 | 0.0008 | 0.0044 | 200 |
| parse_step_type | 0.0012 | 0.0012 | 0.0013 | 0.0011 | 0.0058 | 200 |
| parse_step_wait_for | 0.0011 | 0.0011 | 0.0012 | 0.0010 | 0.0059 | 200 |
| parse_step_with_effects | 0.0083 | 0.0081 | 0.0084 | 0.0079 | 0.0300 | 200 |
| registry_init_register | 0.0045 | 0.0044 | 0.0046 | 0.0043 | 0.0153 | 200 |
| registry_lookup_browser | 0.0015 | 0.0015 | 0.0018 | 0.0013 | 0.0047 | 200 |
| registry_lookup_post | 0.0013 | 0.0012 | 0.0017 | 0.0012 | 0.0034 | 200 |
| scenario_dry_run | 0.0051 | 0.0047 | 0.0056 | 0.0044 | 0.0193 | 100 |
| scenario_orch_init | 0.0002 | 0.0002 | 0.0002 | 0.0001 | 0.0008 | 100 |
| screenshot | 0.0053 | 0.0038 | 0.0058 | 0.0036 | 0.3328 | 500 |
| screenshot_describe | 0.0003 | 0.0003 | 0.0003 | 0.0001 | 0.0245 | 500 |
| scroll | 0.0048 | 0.0036 | 0.0092 | 0.0034 | 0.1108 | 500 |
| scroll_describe | 0.0002 | 0.0002 | 0.0002 | 0.0001 | 0.0023 | 500 |
| type | 0.0051 | 0.0031 | 0.0090 | 0.0030 | 0.2735 | 500 |
| type_describe | 0.0002 | 0.0002 | 0.0003 | 0.0002 | 0.0012 | 500 |
| wait_for | 0.0043 | 0.0031 | 0.0043 | 0.0029 | 0.3622 | 500 |
| wait_for_describe | 0.0003 | 0.0003 | 0.0003 | 0.0002 | 0.0035 | 500 |
| yaml_load_and_parse | 1.0751 | 1.0774 | 1.1558 | 1.0073 | 1.3380 | 100 |

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
