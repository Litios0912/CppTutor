package com.cpptutor;

import android.app.Activity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public class QuizActivity extends Activity {

    private JSONArray questions;
    private int currentIndex = 0;
    private int score = 0;
    private boolean answered = false;

    private TextView questionNumber, questionText, resultText;
    private Button optionA, optionB, optionC, optionD, btnNext;
    private LinearLayout optionsLayout, root;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        loadQuestions();

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xFF121212);
        scroll.setPadding(32, 32, 32, 32);

        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);

        questionNumber = new TextView(this);
        questionNumber.setTextSize(14);
        questionNumber.setTextColor(0xFF00BCD4);
        root.addView(questionNumber);

        questionText = new TextView(this);
        questionText.setTextSize(18);
        questionText.setTextColor(0xFFFFFFFF);
        questionText.setPadding(0, 16, 0, 32);
        root.addView(questionText);

        optionsLayout = new LinearLayout(this);
        optionsLayout.setOrientation(LinearLayout.VERTICAL);

        optionA = createOptionButton();
        optionB = createOptionButton();
        optionC = createOptionButton();
        optionD = createOptionButton();

        optionsLayout.addView(optionA);
        optionsLayout.addView(optionB);
        optionsLayout.addView(optionC);
        optionsLayout.addView(optionD);
        root.addView(optionsLayout);

        resultText = new TextView(this);
        resultText.setTextSize(18);
        resultText.setGravity(Gravity.CENTER);
        resultText.setPadding(0, 16, 0, 16);
        resultText.setVisibility(View.GONE);

        LinearLayout.LayoutParams resParams = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT);
        resParams.setMargins(0, 24, 0, 0);
        resultText.setLayoutParams(resParams);
        root.addView(resultText);

        btnNext = new Button(this);
        btnNext.setText("Siguiente");
        btnNext.setTextSize(16);
        btnNext.setTextColor(0xFFFFFFFF);
        btnNext.setBackgroundColor(0xFF2D2D2D);
        btnNext.setVisibility(View.GONE);
        btnNext.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                currentIndex++;
                showQuestion();
            }
        });
        root.addView(btnNext);

        scroll.addView(root);
        setContentView(scroll);

        showQuestion();
    }

    private Button createOptionButton() {
        Button btn = new Button(this);
        btn.setTextSize(16);
        btn.setTextColor(0xFFFFFFFF);
        btn.setBackgroundColor(0xFF2D2D2D);
        btn.setPadding(32, 20, 32, 20);
        btn.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 0, 0, 8);
        btn.setLayoutParams(params);
        btn.setOnClickListener(new View.OnClickListener() {
            public void onClick(View v) {
                onOptionClick(v);
            }
        });
        return btn;
    }

    private void loadQuestions() {
        try {
            InputStream is = getAssets().open("quizzes.json");
            byte[] buffer = new byte[is.available()];
            is.read(buffer);
            is.close();
            String json = new String(buffer, StandardCharsets.UTF_8);
            questions = new JSONArray(json);
        } catch (Exception e) {
            questions = new JSONArray();
        }
    }

    private void showQuestion() {
        if (currentIndex >= questions.length()) {
            questionNumber.setText("Fin del Quiz!");
            questionText.setText("Puntuacion: " + score + "/" + questions.length());
            optionsLayout.setVisibility(View.GONE);
            resultText.setVisibility(View.VISIBLE);
            resultText.setTextColor(0xFF00BCD4);
            if (score == questions.length()) {
                resultText.setText("Perfecto! Dominas C/C++!");
            } else if (score >= questions.length() / 2) {
                resultText.setText("Buen trabajo! Sigue practicando.");
            } else {
                resultText.setText("Sigue estudiando, tu puedes!");
            }
            btnNext.setVisibility(View.GONE);
            return;
        }

        answered = false;
        btnNext.setVisibility(View.GONE);
        resultText.setVisibility(View.GONE);
        optionsLayout.setVisibility(View.VISIBLE);

        try {
            JSONObject q = questions.getJSONObject(currentIndex);
            questionNumber.setText("Pregunta " + (currentIndex + 1) + "/" + questions.length());
            questionText.setText(q.getString("question"));
            optionA.setText("A: " + q.getString("optionA"));
            optionB.setText("B: " + q.getString("optionB"));
            optionC.setText("C: " + q.getString("optionC"));
            optionD.setText("D: " + q.getString("optionD"));

            resetButtonColors();
        } catch (Exception e) {
            questionText.setText("Error: " + e.getMessage());
        }
    }

    public void onOptionClick(View v) {
        if (answered || questions.length() == 0) return;
        answered = true;

        Button clicked = (Button) v;
        String selected = "";
        if (clicked == optionA) selected = "A";
        else if (clicked == optionB) selected = "B";
        else if (clicked == optionC) selected = "C";
        else if (clicked == optionD) selected = "D";

        try {
            JSONObject q = questions.getJSONObject(currentIndex);
            String correct = q.getString("correct");
            boolean isCorrect = selected.equals(correct);

            if (isCorrect) {
                clicked.setBackgroundColor(0xFF4CAF50);
                resultText.setText("Correcto!");
                resultText.setTextColor(0xFF4CAF50);
                score++;
            } else {
                clicked.setBackgroundColor(0xFFF44336);
                highlightCorrect(correct);
                resultText.setText("Incorrecto. La respuesta era " + correct);
                resultText.setTextColor(0xFFF44336);
            }
            resultText.setVisibility(View.VISIBLE);
            btnNext.setVisibility(View.VISIBLE);

        } catch (Exception e) {
            resultText.setText("Error: " + e.getMessage());
            resultText.setVisibility(View.VISIBLE);
        }
    }

    private void highlightCorrect(String correct) {
        Button correctBtn = null;
        if (correct.equals("A")) correctBtn = optionA;
        else if (correct.equals("B")) correctBtn = optionB;
        else if (correct.equals("C")) correctBtn = optionC;
        else if (correct.equals("D")) correctBtn = optionD;
        if (correctBtn != null) {
            correctBtn.setBackgroundColor(0xFF4CAF50);
        }
    }

    private void resetButtonColors() {
        optionA.setBackgroundColor(0xFF2D2D2D);
        optionB.setBackgroundColor(0xFF2D2D2D);
        optionC.setBackgroundColor(0xFF2D2D2D);
        optionD.setBackgroundColor(0xFF2D2D2D);
    }
}
