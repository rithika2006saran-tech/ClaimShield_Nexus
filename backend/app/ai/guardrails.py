import logging
from typing import Optional

logger = logging.getLogger(__name__)

analyzer = None
anonymizer = None

def init_guardrails():
    """Initialize the Presidio analyzer and anonymizer for PII/PHI protection."""
    global analyzer, anonymizer
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine
        
        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        
        anonymizer = AnonymizerEngine()
        logger.info("Presidio Guardrails initialized for data privacy.")
    except Exception as e:
        logger.warning(f"Failed to initialize Presidio Guardrails: {e}")

def protect_privacy(text: str) -> str:
    """Redact PII/PHI from text using Presidio."""
    if not text or not analyzer or not anonymizer:
        return text
    try:
        results = analyzer.analyze(text=text, language="en")
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        return anonymized.text
    except Exception as e:
        logger.error(f"Guardrail anonymization failed: {e}")
        return text
