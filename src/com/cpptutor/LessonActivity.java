package com.cpptutor;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;

public class LessonActivity extends Activity {

    private JSONArray lessons;
    private ArrayList<String> titles = new ArrayList<String>();
    private ArrayList<String> descriptions = new ArrayList<String>();
    private ArrayList<String> contents = new ArrayList<String>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        loadLessons();

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xFF121212);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 32, 32, 32);

        for (int i = 0; i < titles.size(); i++) {
            final int index = i;
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setBackgroundColor(0xFF2D2D2D);
            card.setPadding(24, 20, 24, 20);
            card.setClickable(true);
            card.setFocusable(true);

            LinearLayout.LayoutParams cardParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
            cardParams.setMargins(0, 0, 0, 12);
            card.setLayoutParams(cardParams);

            TextView tvTitle = new TextView(this);
            tvTitle.setText(titles.get(i));
            tvTitle.setTextSize(18);
            tvTitle.setTextColor(0xFFFFFFFF);
            tvTitle.setTypeface(null, android.graphics.Typeface.BOLD);
            card.addView(tvTitle);

            TextView tvDesc = new TextView(this);
            tvDesc.setText(descriptions.get(i));
            tvDesc.setTextSize(14);
            tvDesc.setTextColor(0xFFB0B0B0);
            tvDesc.setPadding(0, 8, 0, 0);
            card.addView(tvDesc);

            card.setOnClickListener(new View.OnClickListener() {
                public void onClick(View v) {
                    Intent intent = new Intent(LessonActivity.this, LessonDetailActivity.class);
                    intent.putExtra("title", titles.get(index));
                    intent.putExtra("content", contents.get(index));
                    startActivity(intent);
                }
            });

            root.addView(card);
        }

        scroll.addView(root);
        setContentView(scroll);
    }

    private void loadLessons() {
        try {
            InputStream is = getAssets().open("lessons.json");
            byte[] buffer = new byte[is.available()];
            is.read(buffer);
            is.close();
            String json = new String(buffer, StandardCharsets.UTF_8);
            lessons = new JSONArray(json);
            for (int i = 0; i < lessons.length(); i++) {
                JSONObject lesson = lessons.getJSONObject(i);
                titles.add(lesson.getString("title"));
                descriptions.add(lesson.getString("description"));
                contents.add(lesson.getString("content"));
            }
        } catch (Exception e) {
            titles.add("Error");
            descriptions.add("No se pudieron cargar las lecciones");
            contents.add("Error: " + e.getMessage());
        }
    }
}
