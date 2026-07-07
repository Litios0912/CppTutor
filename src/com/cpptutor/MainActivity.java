package com.cpptutor;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 48, 32, 32);
        root.setBackgroundColor(0xFF121212);

        TextView title = new TextView(this);
        title.setText("C++ Tutor");
        title.setTextSize(32);
        title.setTextColor(0xFFFFFFFF);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Aprende C y C++ de forma interactiva");
        subtitle.setTextSize(16);
        subtitle.setTextColor(0xFFB0B0B0);
        subtitle.setPadding(0, 0, 0, 48);
        root.addView(subtitle);

        root.addView(createMenuButton("Lecciones", new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(MainActivity.this, LessonActivity.class));
            }
        }));
        root.addView(createMenuButton("Editor de Codigo", new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(MainActivity.this, CodeEditorActivity.class));
            }
        }));
        root.addView(createMenuButton("Quizzes", new View.OnClickListener() {
            public void onClick(View v) {
                startActivity(new Intent(MainActivity.this, QuizActivity.class));
            }
        }));

        final TextView serverStatus = new TextView(this);
        serverStatus.setText("Servidor de compilacion: offline");
        serverStatus.setTextColor(0xFFFF9800);
        serverStatus.setTextSize(14);
        serverStatus.setGravity(android.view.Gravity.CENTER);
        serverStatus.setPadding(0, 32, 0, 0);
        root.addView(serverStatus);

        setContentView(root);
    }

    private Button createMenuButton(String text, View.OnClickListener listener) {
        Button btn = new Button(this);
        btn.setText(text);
        btn.setTextSize(18);
        btn.setTextColor(0xFFFFFFFF);
        btn.setBackgroundColor(0xFF2D2D2D);
        btn.setPadding(32, 24, 32, 24);
        btn.setOnClickListener(listener);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, 16);
        btn.setLayoutParams(params);
        return btn;
    }
}
