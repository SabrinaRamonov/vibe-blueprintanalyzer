import { useState } from "react";
import "@/App.css";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Upload, Download, Loader2, FileText } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (selectedFile) => {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg'];
    
    if (!validTypes.includes(selectedFile.type)) {
      toast.error('Please upload a PDF or image file (PNG, JPG)');
      return;
    }
    
    if (selectedFile.size > 20 * 1024 * 1024) {
      toast.error('File size must be less than 20MB');
      return;
    }
    
    setFile(selectedFile);
    setResult(null);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const analyzeBlueprint = async () => {
    if (!file) {
      toast.error('Please select a file first');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post(`${API}/analyze-blueprint`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minute timeout
      });

      setResult(response.data);
      
      // Check if analysis had issues
      const analysis = response.data.analysis;
      if (analysis?.error === 'image_processing_failed') {
        toast.warning('Analysis completed with limitations. Try a clearer image for better results.');
      } else if (analysis?.dimensions?.length === 0) {
        toast.warning('No dimensions detected. The blueprint may need better contrast or resolution.');
      } else {
        toast.success('Blueprint analyzed successfully!');
      }
    } catch (error) {
      console.error('Error analyzing blueprint:', error);
      toast.error(error.response?.data?.detail || 'Failed to analyze blueprint');
    } finally {
      setLoading(false);
    }
  };

  const downloadAnnotatedImage = () => {
    if (!result?.annotated_image) return;
    
    const link = document.createElement('a');
    link.href = result.annotated_image;
    link.download = `annotated_${result.filename || 'blueprint'}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Download started!');
  };

  return (
    <div className="app-container">
      <div className="content-wrapper">
        {/* Header */}
        <div className="header-section">
          <div className="header-content">
            <div className="logo-section">
              <div className="logo-icon">
                <FileText size={32} strokeWidth={2.5} />
              </div>
              <h1 className="app-title" data-testid="app-title">Digital Measure</h1>
            </div>
            <p className="app-subtitle">AI-Powered Blueprint Dimension Analyzer</p>
          </div>
        </div>

        {/* Main Content */}
        <div className="main-content">
          {/* Upload Section */}
          {!result && (
            <Card className="upload-card" data-testid="upload-card">
              <CardHeader>
                <CardTitle>Upload Blueprint</CardTitle>
                <CardDescription>
                  Upload a PDF or image of your construction blueprint. Our AI will detect dimensions, identify scale, and estimate missing measurements.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  className={`upload-zone ${dragActive ? 'drag-active' : ''} ${file ? 'has-file' : ''}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  data-testid="upload-zone"
                >
                  <input
                    type="file"
                    id="file-input"
                    className="file-input"
                    accept=".pdf,.png,.jpg,.jpeg"
                    onChange={handleFileInputChange}
                    data-testid="file-input"
                  />
                  <label htmlFor="file-input" className="upload-label">
                    <Upload className="upload-icon" size={48} />
                    {file ? (
                      <div className="file-info">
                        <p className="file-name" data-testid="file-name">{file.name}</p>
                        <p className="file-size">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                      </div>
                    ) : (
                      <div className="upload-text">
                        <p className="upload-primary">Drop your blueprint here or click to browse</p>
                        <p className="upload-secondary">Supports PDF, PNG, JPG (max 20MB)</p>
                      </div>
                    )}
                  </label>
                </div>

                <Button
                  onClick={analyzeBlueprint}
                  disabled={!file || loading}
                  className="analyze-button"
                  size="lg"
                  data-testid="analyze-button"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Analyzing Blueprint...
                    </>
                  ) : (
                    'Analyze Blueprint'
                  )}
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Results Section */}
          {result && (
            <div className="results-section" data-testid="results-section">
              <div className="results-header">
                <h2 className="results-title">Analysis Results</h2>
                <div className="results-actions">
                  <Button
                    onClick={downloadAnnotatedImage}
                    variant="default"
                    data-testid="download-button"
                  >
                    <Download size={18} />
                    Download Annotated
                  </Button>
                  <Button
                    onClick={() => {
                      setResult(null);
                      setFile(null);
                    }}
                    variant="outline"
                    data-testid="new-analysis-button"
                  >
                    New Analysis
                  </Button>
                </div>
              </div>

              {/* Images Comparison */}
              <div className="images-grid">
                <Card data-testid="original-image-card">
                  <CardHeader>
                    <CardTitle>Original Blueprint</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <img
                      src={result.original_image}
                      alt="Original blueprint"
                      className="blueprint-image"
                      data-testid="original-image"
                    />
                  </CardContent>
                </Card>

                <Card data-testid="annotated-image-card">
                  <CardHeader>
                    <CardTitle>Annotated with Dimensions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <img
                      src={result.annotated_image}
                      alt="Annotated blueprint"
                      className="blueprint-image"
                      data-testid="annotated-image"
                    />
                  </CardContent>
                </Card>
              </div>

              {/* Analysis Details */}
              <Card className="analysis-details" data-testid="analysis-details-card">
                <CardHeader>
                  <CardTitle>Detected Dimensions</CardTitle>
                  <CardDescription>
                    Scale: {result.analysis.scale || 'Not detected'} 
                    <span className={`confidence-badge ${result.analysis.scale_confidence || 'low'}`}>
                      {result.analysis.scale_confidence || 'low'} confidence
                    </span>
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {result.analysis.dimensions && result.analysis.dimensions.length > 0 ? (
                    <div className="dimensions-list">
                      {result.analysis.dimensions.map((dim, idx) => (
                        <div
                          key={idx}
                          className={`dimension-item ${dim.type}`}
                          data-testid={`dimension-item-${idx}`}
                        >
                          <div className="dimension-header">
                            <span className="dimension-label">{dim.label}</span>
                            <span className={`dimension-badge ${dim.type}`}>
                              {dim.type}
                            </span>
                          </div>
                          <div className="dimension-value" data-testid={`dimension-value-${idx}`}>
                            {dim.value}
                          </div>
                          {dim.notes && (
                            <div className="dimension-notes">{dim.notes}</div>
                          )}
                          <div className={`confidence-indicator ${dim.confidence}`}>
                            {dim.confidence} confidence
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="no-dimensions">No dimensions detected</p>
                  )}

                  {result.analysis.notes && (
                    <div className="analysis-notes">
                      <h4>Analysis Notes:</h4>
                      <p>{result.analysis.notes}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
