package com.kinoa.studio
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView
import android.graphics.Typeface
import android.app.Activity

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(48,72,48,48) }
        val logo=TextView(this).apply { text="KINOA"; textSize=34f; typeface=Typeface.DEFAULT_BOLD }
        val title=TextView(this).apply { text="AI FILM STUDIO"; textSize=18f }
        val status=TextView(this).apply { text="Studio mobile prêt — connectez ce client au backend KINOA."; textSize=16f; setPadding(0,32,0,0) }
        root.addView(logo); root.addView(title); root.addView(status); setContentView(root)
    }
}
