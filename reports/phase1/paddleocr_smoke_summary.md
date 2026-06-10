# PaddleOCR End-to-End Smoke

- paddleocr: 3.6.0
- paddlepaddle: 3.3.1
- device: CPU
- detection model: PP-OCRv5 server detection
- recognition model: English PP-OCRv5 mobile recognition
- input source: ModelScope SROIE training images
- sample_count: 3

| sample_id | token_count | average_confidence |
| --- | ---: | ---: |
| X00016469612 | 45 | 0.9301 |
| X00016469619 | 46 | 0.9540 |
| X00016469620 | 48 | 0.9807 |

The smoke confirms the image -> PaddleOCR -> normalized OCRToken path. Only the first five tokens were printed during execution; full receipt text is not stored in this report.
