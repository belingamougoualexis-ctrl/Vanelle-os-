package com.cineforge.studio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FilmConfigTest {
    @Test
    fun acceptsSupportedFilmSettings() {
        assertNull(FilmConfig(
            prompt = "Une rue de Douala sous une pluie réaliste, caméra à l'épaule",
            seconds = 8,
            width = 768,
            height = 512
        ).validationError())
    }

    @Test
    fun rejectsBlankOrTooShortPrompts() {
        assertEquals(
            "Décris la scène avec au moins 12 caractères.",
            FilmConfig("pluie", 5, 512, 320).validationError()
        )
    }

    @Test
    fun rejectsUnsupportedResolution() {
        assertEquals(
            "Résolution non prise en charge par ce profil.",
            FilmConfig("Une scène de film réaliste", 5, 1024, 576).validationError()
        )
    }

    @Test
    fun rejectsDurationOutsideModelProfile() {
        assertEquals(
            "La durée doit être comprise entre 5 et 10 secondes.",
            FilmConfig("Une scène de film réaliste", 11, 512, 320).validationError()
        )
    }
}
