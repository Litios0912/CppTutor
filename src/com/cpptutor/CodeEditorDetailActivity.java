package com.cpptutor;

import android.app.Activity;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public class CodeEditorDetailActivity extends Activity {
    private WebView webView;
    private TextView outputText;
    private Handler handler;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        String title = getIntent().getStringExtra("title");
        final String description = getIntent().getStringExtra("description");
        final String starterCode = getIntent().getStringExtra("starterCode");

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xFF121212);

        TextView tvTitle = new TextView(this);
        tvTitle.setText(title);
        tvTitle.setTextSize(20);
        tvTitle.setTextColor(0xFFFFFFFF);
        tvTitle.setTypeface(null, Typeface.BOLD);
        tvTitle.setPadding(32, 24, 32, 8);
        root.addView(tvTitle);

        final TextView tvDesc = new TextView(this);
        tvDesc.setText(description);
        tvDesc.setTextSize(14);
        tvDesc.setTextColor(0xFFB0B0B0);
        tvDesc.setPadding(32, 0, 32, 8);
        root.addView(tvDesc);

        webView = new WebView(this);
        LinearLayout.LayoutParams webParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1);
        webView.setLayoutParams(webParams);

        outputText = new TextView(this);
        outputText.setText("Presiona Compilar para ejecutar tu codigo");
        outputText.setTextSize(12);
        outputText.setTextColor(0xFF4CAF50);
        outputText.setPadding(16, 12, 16, 12);
        outputText.setBackgroundColor(0xFF1E1E1E);
        outputText.setTypeface(Typeface.MONOSPACE);
        LinearLayout.LayoutParams outParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 300);
        outputText.setLayoutParams(outParams);

        handler = new Handler(Looper.getMainLooper());
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            public void onPageFinished(WebView view, String url) {
                String escaped = JSONString(starterCode);
                webView.evaluateJavascript("setCode(" + escaped + ")", null);
                tvDesc.setText(description);
            }
        });
        webView.addJavascriptInterface(new CompileInterface(), "AndroidBridge");
        root.addView(webView);
        root.addView(outputText);
        setContentView(root);
        webView.loadUrl("file:///android_asset/editor.html");
    }

    private class CompileInterface {
        @JavascriptInterface
        public void compile(final String code, final String language) {
            new Thread(new Runnable() {
                public void run() {
                    try {
                        final String json = "{\"code\":" + JSONString(code) + ",\"lang\":\"" + language + "\"}";
                        URL url = new URL("http://127.0.0.1:8080/compile");
                        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                        conn.setRequestMethod("POST");
                        conn.setRequestProperty("Content-Type", "application/json");
                        conn.setDoOutput(true);
                        conn.setConnectTimeout(10000);
                        conn.setReadTimeout(30000);
                        OutputStream os = conn.getOutputStream();
                        os.write(json.getBytes(StandardCharsets.UTF_8));
                        os.flush();
                        os.close();
                        java.util.Scanner sc;
                        if (conn.getResponseCode() == 200) {
                            sc = new java.util.Scanner(conn.getInputStream());
                        } else {
                            sc = new java.util.Scanner(conn.getErrorStream());
                        }
                        final String result = sc.useDelimiter("\\A").hasNext() ? sc.next() : "";
                        sc.close();
                        conn.disconnect();
                        handler.post(new Runnable() {
                            public void run() {
                                outputText.setText(result);
                                webView.evaluateJavascript("showOutput(" + JSONString(result) + ")", null);
                            }
                        });
                    } catch (final Exception e) {
                        handler.post(new Runnable() {
                            public void run() {
                                String err = "Error: " + e.getMessage();
                                outputText.setText(err);
                                outputText.setTextColor(0xFFF44336);
                            }
                        });
                    }
                }
            }).start();
        }
    }

    private String JSONString(String s) {
        if (s == null) return "\"\"";
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"")
            .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }
}
