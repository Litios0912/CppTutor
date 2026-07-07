package com.cpptutor;

import android.app.Activity;
import android.os.Bundle;
import android.text.Html;
import android.widget.ScrollView;
import android.widget.TextView;

public class LessonDetailActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        String title = getIntent().getStringExtra("title");
        String content = getIntent().getStringExtra("content");
        setTitle(title);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xFF121212);
        scroll.setPadding(32, 32, 32, 32);

        TextView tv = new TextView(this);
        tv.setText(Html.fromHtml(content));
        tv.setTextSize(16);
        tv.setTextColor(0xFFFFFFFF);
        tv.setLineSpacing(8, 1);

        scroll.addView(tv);
        setContentView(scroll);
    }
}
