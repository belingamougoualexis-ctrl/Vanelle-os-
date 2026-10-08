package com.kinoa.studio
import android.app.Activity
import android.os.Bundle
import android.graphics.Typeface
import android.widget.*
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : Activity() {
    private val baseUrl = "http://10.0.2.2:8000"
    private lateinit var status: TextView
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root=LinearLayout(this).apply { orientation=LinearLayout.VERTICAL; setPadding(48,72,48,48) }
        val logo=TextView(this).apply { text="KINOA"; textSize=34f; typeface=Typeface.DEFAULT_BOLD }
        val title=TextView(this).apply { text="AI FILM STUDIO"; textSize=18f }
        status=TextView(this).apply { text="Connexion au backend KINOA…"; textSize=16f; setPadding(0,32,0,24) }
        val refresh=Button(this).apply { text="Vérifier le moteur"; setOnClickListener { checkBackend() } }
        root.addView(logo); root.addView(title); root.addView(status); root.addView(refresh)
        setContentView(root); checkBackend()
    }
    private fun checkBackend() {
        status.text="Vérification…"
        thread {
            try {
                val conn=URL("$baseUrl/health").openConnection() as HttpURLConnection
                conn.connectTimeout=3000; conn.readTimeout=3000
                val code=conn.responseCode
                val body=conn.inputStream.bufferedReader().readText()
                conn.disconnect()
                runOnUiThread { status.text=if(code==200) "Backend KINOA connecté\n$body" else "Backend HTTP $code" }
            } catch(ex:Exception) {
                runOnUiThread { status.text="Backend indisponible : "+ex.message }
            }
        }
    }
}
