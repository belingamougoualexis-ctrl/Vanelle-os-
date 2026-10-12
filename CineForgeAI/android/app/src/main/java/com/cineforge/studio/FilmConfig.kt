package com.cineforge.studio

data class FilmConfig(
    val prompt: String,
    val seconds: Int,
    val width: Int,
    val height: Int,
    val fps: Int = 24
) {
    fun validationError(): String? {
        if (prompt.trim().length < 12) return "Décris la scène avec au moins 12 caractères."
        if (prompt.length > 2500) return "Le prompt ne doit pas dépasser 2 500 caractères."
        if (seconds !in 5..10) return "La durée doit être comprise entre 5 et 10 secondes."
        if ((width to height) !in setOf(512 to 320, 768 to 512)) {
            return "Résolution non prise en charge par ce profil."
        }
        if (fps != 24) return "La cadence prise en charge est de 24 images/s."
        return null
    }
}
