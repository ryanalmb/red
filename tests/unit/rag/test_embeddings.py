"""Unit tests for RAG embeddings."""
import pytest
from unittest.mock import patch, MagicMock
from cyberred.rag.embeddings import RAGEmbeddings


@pytest.mark.unit
class TestRAGEmbeddings:
    """Tests for RAGEmbeddings class."""
    
    def test_constants_defined(self) -> None:
        """Required model constants are defined."""
        assert RAGEmbeddings.PRIMARY_MODEL == "basel/ATTACK-BERT"
        assert RAGEmbeddings.FALLBACK_MODEL == "sentence-transformers/all-mpnet-base-v2"
        assert RAGEmbeddings.EMBEDDING_DIM == 768

    def test_initialization_state(self) -> None:
        """Model should be None (lazy loaded) upon initialization."""
        embeddings = RAGEmbeddings()
        assert embeddings._model is None
        assert embeddings._model_name is None
        assert not embeddings.is_loaded

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_lazy_loading(self, mock_cls: MagicMock) -> None:
        """Model loads only on first use."""
        embeddings = RAGEmbeddings()
        # Verify not loaded yet
        assert embeddings._model is None
        mock_cls.assert_not_called()

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_encode_loads_model(self, mock_cls: MagicMock) -> None:
        """encode() triggers model loading."""
        mock_model = MagicMock()
        # Mock numpy array result which has .tolist()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        result = embeddings.encode("test")
        
        assert embeddings.is_loaded
        mock_cls.assert_called_once_with("basel/ATTACK-BERT", device="cpu")
        mock_model.encode.assert_called_once()
        assert len(result) == 768

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_encode_fallback(self, mock_cls: MagicMock) -> None:
        """Fallback model is used if primary fails."""
        # Side effect: first call raises, second call succeeds
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        
        def side_effect(*args, **kwargs):
            if args and args[0] == "basel/ATTACK-BERT":
                raise ValueError("Model not found")
            return mock_model
            
        mock_cls.side_effect = side_effect
        
        embeddings = RAGEmbeddings()
        embeddings.encode("test")
        
        assert embeddings._model_name == RAGEmbeddings.FALLBACK_MODEL
        assert mock_cls.call_count == 2

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    @patch("cyberred.rag.embeddings.log")
    def test_encode_batch_efficiency(self, mock_log: MagicMock, mock_cls: MagicMock) -> None:
        """Batch encoding uses efficient path and logs for large batches."""
        mock_model = MagicMock()
        # Mock numpy array result which has .tolist()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [[0.1] * 768, [0.1] * 768]
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        results = embeddings.encode_batch(["t1", "t2"])
        
        mock_model.encode.assert_called_once_with(["t1", "t2"], convert_to_numpy=True)
        assert len(results) == 2
        assert len(results[0]) == 768

    def test_encode_batch_large_logging(self) -> None:
        """Large batches trigger logging."""
        with patch("cyberred.rag.embeddings.SentenceTransformer") as mock_cls, \
             patch("cyberred.rag.embeddings.log") as mock_log:
            mock_model = MagicMock()
            mock_array = MagicMock()
            mock_array.tolist.return_value = []
            mock_model.encode.return_value = mock_array
            mock_cls.return_value = mock_model
            
            embeddings = RAGEmbeddings()
            # Threshold is > 100
            texts = ["t"] * 101
            embeddings.encode_batch(texts)
            
            mock_log.info.assert_called_once()
            args = mock_log.info.call_args
            assert args[0][0] == "rag_embeddings_batch_start"
            assert args[1]["count"] == 101

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_encode_empty_string(self, mock_cls: MagicMock) -> None:
        """encode() handles empty string gracefully."""
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.0] * 768
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        result = embeddings.encode("")
        
        assert len(result) == 768
        mock_model.encode.assert_called_once_with("", convert_to_numpy=True)

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_second_encode_reuses_cached_model(self, mock_cls: MagicMock) -> None:
        """Second encode() call reuses cached model (no reload)."""
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        # First call loads model
        embeddings.encode("first")
        # Second call should reuse
        embeddings.encode("second")
        
        # Model only loaded once
        mock_cls.assert_called_once()
        # But encode called twice
        assert mock_model.encode.call_count == 2

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    @patch("cyberred.rag.embeddings.log")
    def test_fallback_logs_warning(self, mock_log: MagicMock, mock_cls: MagicMock) -> None:
        """Fallback activation logs warning with correct event name."""
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        
        def side_effect(*args, **kwargs):
            if args and args[0] == "basel/ATTACK-BERT":
                raise ValueError("Model not found")
            return mock_model
            
        mock_cls.side_effect = side_effect
        
        embeddings = RAGEmbeddings()
        embeddings.encode("test")
        
        # Verify warning was logged
        mock_log.warning.assert_called_once()
        args = mock_log.warning.call_args
        assert args[0][0] == "rag_embeddings_fallback_activated"
        assert args[1]["primary_model"] == "basel/ATTACK-BERT"

    def test_encode_batch_empty_list(self) -> None:
        """encode_batch([]) returns empty list without loading model."""
        embeddings = RAGEmbeddings()
        result = embeddings.encode_batch([])
        
        assert result == []
        assert not embeddings.is_loaded  # Model should NOT be loaded

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_active_model_property(self, mock_cls: MagicMock) -> None:
        """active_model property returns model name after loading."""
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        # Before loading
        assert embeddings.active_model is None
        
        # After loading
        embeddings.encode("test")
        assert embeddings.active_model == "basel/ATTACK-BERT"

    @patch("cyberred.rag.embeddings.SentenceTransformer")
    def test_load_model_already_loaded_early_return(self, mock_cls: MagicMock) -> None:
        """_load_model() returns early if already loaded (line 31 coverage)."""
        mock_model = MagicMock()
        mock_array = MagicMock()
        mock_array.tolist.return_value = [0.1] * 768
        mock_model.encode.return_value = mock_array
        mock_cls.return_value = mock_model
        
        embeddings = RAGEmbeddings()
        # First load
        embeddings._load_model()
        assert mock_cls.call_count == 1
        
        # Second load should early return
        embeddings._load_model()
        assert mock_cls.call_count == 1  # Still 1, not called again
