"""Validate all pages and cache round-trip before rebuilding the live index."""
import sys
import tempfile
import time
from pathlib import Path
from document_ingestion import IngestionSettings, OCRResultCache, load_and_chunk_document
from tesseract_service import TesseractOCRService

service = TesseractOCRService()
with tempfile.TemporaryDirectory() as directory:
    cache = OCRResultCache(Path(directory))
    settings = IngestionSettings(dpi=300)
    started = time.perf_counter()
    first = load_and_chunk_document(Path(sys.argv[1]), service, settings, cache)
    elapsed = time.perf_counter() - started
    second = load_and_chunk_document(Path(sys.argv[1]), service, settings, cache)
    assert [d.page_content for d in first.chunks] == [d.page_content for d in second.chunks]
    assert not second.created_cache_files
    assert {d.metadata['page'] for d in first.chunks} == set(range(5))
    third_page = ' '.join(d.page_content for d in first.chunks if d.metadata['page'] == 2)
    for phrase in ('5.000.000 (Năm triệu đồng chẵn)', '7.000.000 (Bảy triệu đồng chẵn)'):
        assert phrase in third_page, phrase
    assert all(d.metadata['extraction_method'] == 'tesseract' for d in first.chunks)
    print('PASS pages=5 chunks=', len(first.chunks), 'seconds=', round(elapsed, 2), 'cache_reused=True')
    print(service.cache_fingerprint)
