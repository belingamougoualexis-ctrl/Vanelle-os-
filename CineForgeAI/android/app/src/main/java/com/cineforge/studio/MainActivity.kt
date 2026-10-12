package com.cineforge.studio

import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Divider
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val Ink = Color(0xFF080B14)
private val Panel = Color(0xFF111827)
private val PanelSoft = Color(0xFF192438)
private val Accent = Color(0xFF78A8FF)
private val AccentViolet = Color(0xFFB69CFF)
private val Muted = Color(0xFFA8B5CA)
private val Good = Color(0xFF8DE0BA)
private val Warning = Color(0xFFFFCF8A)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Accent,
                    secondary = AccentViolet,
                    background = Ink,
                    surface = Panel,
                    onPrimary = Ink,
                    onBackground = Color(0xFFF4F7FF),
                    onSurface = Color(0xFFF4F7FF)
                )
            ) {
                CineForgeScreen()
            }
        }
    }
}

@Composable
private fun CineForgeScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var server by rememberSaveable { mutableStateOf("http://192.168.1.20:8765") }
    var token by rememberSaveable { mutableStateOf("") }
    var prompt by rememberSaveable {
        mutableStateOf("Un jeune cinéaste marche dans une rue de Douala après une pluie tropicale. Les motos passent au loin, les vêtements sont légèrement humides, les néons se reflètent dans les flaques. Caméra à l'épaule, mouvement naturel, lumière disponible, visages et textures imparfaits et crédibles.")
    }
    var seconds by rememberSaveable { mutableIntStateOf(5) }
    var width by rememberSaveable { mutableIntStateOf(768) }
    var height by rememberSaveable { mutableIntStateOf(512) }
    var checking by remember { mutableStateOf(false) }
    var generating by remember { mutableStateOf(false) }
    var engineOnline by remember { mutableStateOf(false) }
    var engineInfo by remember { mutableStateOf("Non vérifié") }
    var jobState by remember { mutableStateOf("Aucun rendu lancé") }
    var jobId by remember { mutableStateOf("") }
    var message by remember { mutableStateOf("") }
    var outputUri by rememberSaveable { mutableStateOf("") }
    var outputName by rememberSaveable { mutableStateOf("") }

    fun baseUrl(): String = server.trim().trimEnd('/')

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Ink)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 18.dp, vertical = 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("CINEFORGE", color = Accent, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 3.sp)
                Text("AI STUDIO", color = Color.White, fontSize = 29.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = 1.sp)
                Text("Un atelier cinéma connecté à un vrai moteur vidéo", color = Muted, fontSize = 13.sp)
            }
            Box(
                modifier = Modifier
                    .size(56.dp)
                    .background(PanelSoft, RoundedCornerShape(18.dp)),
                contentAlignment = Alignment.Center
            ) {
                Text("CF", color = AccentViolet, fontSize = 23.sp, fontWeight = FontWeight.Black)
            }
        }

        Card(
            colors = CardDefaults.cardColors(containerColor = Panel),
            shape = RoundedCornerShape(20.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(9.dp).background(if (engineOnline) Good else Warning, RoundedCornerShape(99.dp)))
                    Spacer(Modifier.width(8.dp))
                    Text(if (engineOnline) "MOTEUR CONNECTÉ" else "MOTEUR NON CONNECTÉ", color = if (engineOnline) Good else Warning, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
                Text(engineInfo, color = Muted, fontSize = 13.sp)
                Button(
                    onClick = {
                        checking = true
                        message = ""
                        scope.launch {
                            try {
                                val response = withContext(Dispatchers.IO) {
                                    requestJson(baseUrl() + "/health", "GET", null, null)
                                }
                                engineOnline = response.optString("status") == "online"
                                val device = response.optString("device", "inconnu")
                                val gpu = response.optBoolean("cuda_available", false)
                                val model = response.optString("model_id", "LTX-2.5")
                                engineInfo = "$model • calcul détecté : $device" +
                                    if (gpu) " • CUDA détecté" else " • aucun GPU CUDA détecté"
                                message = if (gpu) {
                                    "Serveur joignable. Le modèle sera chargé au lancement du rendu."
                                } else {
                                    "Serveur joignable, mais sans GPU CUDA détecté : le rendu peut être extrêmement lent ou manquer de mémoire."
                                }
                            } catch (e: Exception) {
                                engineOnline = false
                                engineInfo = "Impossible de joindre le serveur. Vérifie l'adresse, le réseau Wi-Fi et le pare-feu du PC."
                                message = e.message ?: "Connexion impossible."
                            } finally {
                                checking = false
                            }
                        }
                    },
                    enabled = !checking && !generating,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(containerColor = PanelSoft, contentColor = Accent)
                ) {
                    if (checking) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = Accent)
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(if (checking) "Vérification réelle…" else "Tester le moteur")
                }
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            SectionTitle("01 / SCÈNE")
            Text("Décris ce que la caméra doit filmer. Les détails de mouvement, de météo, de lumière et d'imperfections aident à obtenir un rendu moins artificiel.", color = Muted, fontSize = 13.sp)
            OutlinedTextField(
                value = prompt,
                onValueChange = { prompt = it; message = "" },
                modifier = Modifier.fillMaxWidth(),
                minLines = 5,
                maxLines = 9,
                label = { Text("Description cinématographique") },
                placeholder = { Text("Personnages, action, décor, objectif, lumière, caméra…") },
                shape = RoundedCornerShape(16.dp)
            )
            Text("${prompt.length} / 2 500 caractères", color = Muted, fontSize = 11.sp)
        }

        Card(
            colors = CardDefaults.cardColors(containerColor = Panel),
            shape = RoundedCornerShape(20.dp),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionTitle("02 / PARAMÈTRES DE PRISE DE VUE")
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("Durée", color = Color.White, fontWeight = FontWeight.SemiBold)
                    Text("$seconds secondes", color = Accent, fontWeight = FontWeight.Bold)
                }
                Slider(
                    value = seconds.toFloat(),
                    onValueChange = { seconds = it.toInt().coerceIn(5, 10) },
                    valueRange = 5f..10f,
                    steps = 4,
                    enabled = !generating
                )
                Text("Résolution de sortie", color = Color.White, fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = width == 512,
                        onClick = { width = 512; height = 320 },
                        label = { Text("512 × 320") },
                        enabled = !generating
                    )
                    FilterChip(
                        selected = width == 768,
                        onClick = { width = 768; height = 512 },
                        label = { Text("768 × 512") },
                        enabled = !generating
                    )
                }
                Text("24 images/s • rendu calculé par LTX-2.5 sur le PC connecté", color = Muted, fontSize = 12.sp)
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            SectionTitle("03 / MOTEUR LOCAL")
            Text("Adresse du serveur sur ton PC et code temporaire affiché dans sa fenêtre de lancement.", color = Muted, fontSize = 13.sp)
            OutlinedTextField(
                value = server,
                onValueChange = { server = it; engineOnline = false },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Adresse du PC") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                shape = RoundedCornerShape(14.dp)
            )
            OutlinedTextField(
                value = token,
                onValueChange = { token = it.trim() },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                label = { Text("Code temporaire du moteur") },
                placeholder = { Text("Copie le code depuis la console du PC") },
                shape = RoundedCornerShape(14.dp)
            )
        }

        Button(
            onClick = {
                val config = FilmConfig(prompt.trim(), seconds, width, height)
                val issue = config.validationError()
                if (issue != null) {
                    message = issue
                } else if (!server.startsWith("http://") && !server.startsWith("https://")) {
                    message = "L'adresse doit commencer par http:// ou https://"
                } else if (token.isBlank()) {
                    message = "Saisis le code temporaire affiché par le moteur sur le PC."
                } else {
                    generating = true
                    message = ""
                    outputUri = ""
                    outputName = ""
                    jobState = "Envoi de la demande…"
                    scope.launch {
                        try {
                            val finalPrompt = "Photorealistic live-action cinema, natural skin pores and subtle imperfections, believable human motion, consistent character appearance and wardrobe, coherent real-world environment, physically plausible lighting, natural camera movement, no glossy CGI look, no text overlays. Scene: ${config.prompt}"
                            val request = JSONObject()
                                .put("prompt", finalPrompt)
                                .put("seconds", config.seconds)
                                .put("width", config.width)
                                .put("height", config.height)
                                .put("fps", config.fps)
                            val created = withContext(Dispatchers.IO) {
                                requestJson(baseUrl() + "/generate", "POST", request, token)
                            }
                            val id = created.getString("job_id")
                            jobId = id
                            jobState = "Travail envoyé • ID ${id.take(8)}"
                            var finished = false
                            for (attempt in 0 until 720) {
                                delay(2500)
                                val status = withContext(Dispatchers.IO) {
                                    requestJson(baseUrl() + "/jobs/$id", "GET", null, token)
                                }
                                when (status.optString("status")) {
                                    "queued" -> jobState = "En attente dans la file du moteur…"
                                    "running" -> jobState = "Le modèle génère réellement les images et l’audio…"
                                    "completed" -> {
                                        jobState = "Rendu terminé • téléchargement du MP4…"
                                        val uri = withContext(Dispatchers.IO) {
                                            downloadAndSaveVideo(context, baseUrl() + "/jobs/$id/video", token)
                                        }
                                        outputUri = uri.toString()
                                        outputName = "CineForge_${id.take(8)}.mp4"
                                        jobState = "MP4 enregistré dans Films/CineForge AI"
                                        message = "Génération terminée et fichier vidéo récupéré depuis le moteur."
                                        finished = true
                                        break
                                    }
                                    "failed" -> throw IOException(status.optString("error", "Le moteur a échoué pendant le rendu."))
                                    else -> jobState = "État reçu du moteur : ${status.optString("status", "inconnu")}"
                                }
                            }
                            if (!finished) throw IOException("Le rendu n'est pas terminé après 30 minutes. Consulte la console du PC.")
                        } catch (e: Exception) {
                            jobState = "Rendu interrompu"
                            message = e.message ?: "Échec inconnu du moteur."
                        } finally {
                            generating = false
                        }
                    }
                }
            },
            enabled = !generating && !checking,
            modifier = Modifier.fillMaxWidth().height(56.dp),
            shape = RoundedCornerShape(16.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent, contentColor = Ink)
        ) {
            if (generating) {
                CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Ink)
                Spacer(Modifier.width(10.dp))
                Text("RENDU EN COURS…", fontWeight = FontWeight.ExtraBold)
            } else {
                Text("GÉNÉRER LE FILM MP4", fontWeight = FontWeight.ExtraBold, letterSpacing = 0.5.sp)
            }
        }

        if (jobId.isNotBlank() || jobState != "Aucun rendu lancé") {
            Card(colors = CardDefaults.cardColors(containerColor = PanelSoft), shape = RoundedCornerShape(16.dp)) {
                Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    SectionTitle("ÉTAT DU RENDU")
                    Text(jobState, color = Color.White, fontWeight = FontWeight.SemiBold)
                    if (jobId.isNotBlank()) Text("Identifiant : $jobId", color = Muted, fontSize = 11.sp)
                    if (generating) CircularProgressIndicator(color = Accent, strokeWidth = 3.dp, modifier = Modifier.size(26.dp))
                    if (outputUri.isNotBlank()) {
                        Divider(color = Color(0xFF34435A))
                        Text(outputName, color = Good, fontWeight = FontWeight.Bold)
                        Button(
                            onClick = {
                                try {
                                    val intent = Intent(Intent.ACTION_VIEW).apply {
                                        setDataAndType(Uri.parse(outputUri), "video/mp4")
                                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                    }
                                    context.startActivity(intent)
                                } catch (_: Exception) {
                                    message = "Aucun lecteur vidéo compatible n'est installé."
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Good, contentColor = Ink)
                        ) { Text("Lire le film") }
                    }
                }
            }
        }

        if (message.isNotBlank()) {
            Card(
                colors = CardDefaults.cardColors(containerColor = PanelSoft),
                shape = RoundedCornerShape(14.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(message, modifier = Modifier.padding(14.dp), color = if (message.contains("terminée") || message.contains("joignable")) Good else Warning, fontSize = 13.sp)
            }
        }

        Spacer(Modifier.height(6.dp))
        Divider(color = Color(0xFF28354A))
        Text(
            "Le calcul vidéo n’est pas simulé : l’APK envoie le travail au moteur LTX-2.5 installé sur un PC. La taille du modèle, la RAM et le GPU peuvent limiter ou empêcher le rendu.",
            color = Muted,
            fontSize = 11.sp,
            lineHeight = 16.sp
        )
        Text("CINEFORGE AI STUDIO • Android 8.0+", color = Color(0xFF667791), fontSize = 10.sp)
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(text, color = AccentViolet, fontSize = 12.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.3.sp)
}

private fun requestJson(
    url: String,
    method: String,
    body: JSONObject?,
    token: String?
): JSONObject {
    val connection = (URL(url).openConnection() as HttpURLConnection).apply {
        requestMethod = method
        connectTimeout = 15_000
        readTimeout = 120_000
        setRequestProperty("Accept", "application/json")
        if (!token.isNullOrBlank()) setRequestProperty("X-CineForge-Token", token)
        if (body != null) {
            doOutput = true
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
        }
    }
    try {
        if (body != null) {
            connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        }
        val code = connection.responseCode
        val stream = if (code in 200..299) connection.inputStream else connection.errorStream
        val payload = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
        if (code !in 200..299) {
            val detail = try { JSONObject(payload).optString("detail", payload) } catch (_: Exception) { payload }
            throw IOException("HTTP $code : ${detail.ifBlank { "requête refusée" }}")
        }
        return JSONObject(payload)
    } finally {
        connection.disconnect()
    }
}

private fun downloadAndSaveVideo(context: android.content.Context, url: String, token: String): Uri {
    val connection = (URL(url).openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 15_000
        readTimeout = 120_000
        setRequestProperty("Accept", "video/mp4")
        setRequestProperty("X-CineForge-Token", token)
    }
    try {
        val code = connection.responseCode
        if (code !in 200..299) throw IOException("Téléchargement MP4 refusé (HTTP $code).")
        val filename = "CineForge_${SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())}.mp4"
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, filename)
            put(MediaStore.MediaColumns.MIME_TYPE, "video/mp4")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.MediaColumns.RELATIVE_PATH, "Movies/CineForge AI")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            }
        }
        val uri = context.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Android n'a pas pu créer le fichier MP4.")
        try {
            val output = context.contentResolver.openOutputStream(uri, "w")
                ?: throw IOException("Impossible d'ouvrir le fichier MP4 en écriture.")
            output.use { sink -> connection.inputStream.use { source -> source.copyTo(sink) } }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val complete = ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }
                context.contentResolver.update(uri, complete, null, null)
            }
            return uri
        } catch (e: Exception) {
            context.contentResolver.delete(uri, null, null)
            throw e
        }
    } finally {
        connection.disconnect()
    }
}
