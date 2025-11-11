'use client';

import { useState } from 'react';

export default function SimpleTestPage() {
  const [loading, setLoading] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const [files, setFiles] = useState<any>({});

  const runTest = async (testName: string, endpoint: string) => {
    setLoading(testName);

    try {
      const response = await fetch(`http://127.0.0.1:8000/api/music-tests/${endpoint}`, {
        method: 'POST'
      });

      const result = await response.json();
      setResults(prev => [{ ...result, testName, timestamp: new Date() }, ...prev]);

      // Odśwież listę plików
      loadFiles();

    } catch (error) {
      setResults(prev => [{
        success: false,
        output: '',
        error: `Network error: ${error}`,
        testName,
        timestamp: new Date()
      }, ...prev]);
    } finally {
      setLoading(null);
    }
  };

  const loadFiles = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/music-tests/list-files');
      const data = await response.json();
      setFiles(data);
    } catch (error) {
      console.error('Error loading files:', error);
    }
  };

  return (
    <div className="min-h-screen bg-black text-white p-8">
      <div className="max-w-4xl mx-auto">

        <h1 className="text-3xl font-bold mb-8 text-center">🎵 Music Tests</h1>

        {/* Przyciski */}
        <div className="bg-gray-900 p-6 rounded-lg mb-8">
          <h2 className="text-xl mb-4">Uruchom testy:</h2>

          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => runTest('MIDI Generator', 'run-midi')}
              disabled={loading !== null}
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 p-4 rounded font-bold"
            >
              {loading === 'MIDI Generator' ? '⏳ Running...' : '🎼 Test MIDI'}
            </button>

            <button
              onClick={() => runTest('Sample Fetcher', 'run-samples')}
              disabled={loading !== null}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 p-4 rounded font-bold"
            >
              {loading === 'Sample Fetcher' ? '⏳ Running...' : '🎧 Test Samples'}
            </button>

            <button
              onClick={() => runTest('Audio Synthesizer', 'run-audio')}
              disabled={loading !== null}
              className="bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-600 p-4 rounded font-bold"
            >
              {loading === 'Audio Synthesizer' ? '⏳ Running...' : '🎵 Test Audio'}
            </button>

            <button
              onClick={() => runTest('Full Pipeline', 'run-full')}
              disabled={loading !== null}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 p-4 rounded font-bold"
            >
              {loading === 'Full Pipeline' ? '⏳ Running...' : '🚀 Full Test'}
            </button>
          </div>

          <div className="mt-4">
            <button
              onClick={loadFiles}
              className="bg-gray-600 hover:bg-gray-700 p-2 px-4 rounded"
            >
              📁 Check Files
            </button>
          </div>
        </div>

        {/* Wyniki */}
        {results.map((result, index) => (
          <div key={index} className={`p-4 rounded-lg mb-4 ${result.success ? 'bg-green-900' : 'bg-red-900'}`}>
            <h3 className="font-bold">{result.testName} - {result.success ? '✅ Success' : '❌ Failed'}</h3>
            <small className="text-gray-300">{result.timestamp.toLocaleTimeString()}</small>

            {result.output && (
              <pre className="bg-black p-2 mt-2 rounded text-sm overflow-auto max-h-40">{result.output}</pre>
            )}

            {result.error && (
              <pre className="bg-red-800 p-2 mt-2 rounded text-sm overflow-auto max-h-40">{result.error}</pre>
            )}
          </div>
        ))}

        {/* Lista plików */}
        {Object.keys(files).length > 0 && (
          <div className="bg-gray-900 p-6 rounded-lg">
            <h2 className="text-xl mb-4">Generated Files:</h2>

            {Object.entries(files).map(([type, fileList]: [string, any]) => (
              <div key={type} className="mb-4">
                <h3 className="font-bold capitalize">{type}:</h3>
                {fileList.length === 0 ? (
                  <p className="text-gray-400">No files</p>
                ) : (
                  <ul className="list-disc list-inside text-sm">
                    {fileList.map((file: string, i: number) => (
                      <li key={i} className="text-gray-300">{file}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}