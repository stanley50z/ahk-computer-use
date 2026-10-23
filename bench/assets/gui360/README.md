# GUI-360 Office templates for TB3.x

Unmodified starting documents for TB3.1 and TB3.2, copied from the GUI-360 dataset (`vyokky/GUI-360`, revision `1c46362efaae836c601004e77b98a1aba89a530f`, path `templates/<app>/<file>`). Each trial copies one into its workspace; the copy is what the actor edits.

| File | Source path | SHA-256 | Used by |
|---|---|---|---|
| `adult_sexual_behaviors.xlsx` | `templates/excel/adult_sexual_behaviors.xlsx` | `1b3b5fa4a3b90ce97267e22391296598791a17bb8bc40568137ca6ceb0fc8e61` | TB3.1 |
| `template1.docx` | `templates/word/template1.docx` | `22769330a651229ca666daab61f3c587f709c13d6ef540afd08a7257568a6bd7` | TB3.2 |

## Source and license

Source: [vyokky/GUI-360](https://huggingface.co/datasets/vyokky/GUI-360), with [templates at the pinned revision](https://huggingface.co/datasets/vyokky/GUI-360/tree/1c46362efaae836c601004e77b98a1aba89a530f/templates). The [dataset card at that revision](https://huggingface.co/datasets/vyokky/GUI-360/blob/1c46362efaae836c601004e77b98a1aba89a530f/README.md) states: "This dataset is released under the [MIT License](https://opensource.org/license/mit)." No separate `LICENSE` file is supplied by the dataset at that revision.

The templates remain attributed to their upstream creators; existing document metadata and notices are unchanged. ACU does not relicense them under its own copyright. The dataset's MIT declaration does not independently establish rights in third-party content within a template, or grant Windows/Microsoft Office licenses. Attribution is not a substitute for any required permission.

The spreadsheet holds synthetic demographic rows. GUI-360 ids, requests (TB3.2 adapted) and the file checks are in `bench/tb3.py`; the feasibility study is `docs/reports/gui-360-feasibility.html`.
