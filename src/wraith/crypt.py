"""The Crypt: Hand-crafted offline whispers and deterministic fallback rewrites.

Used whenever the model is unreachable, times out, or produces invalid output.
Ensures zero disruption and consistent ghostly charm even completely offline.
"""

from __future__ import annotations

import random

# At least 20 hand-written whispers per persona across triggers (60+ total)
CRYPT_WHISPERS: dict[str, dict[str, list[str]]] = {
    "poltergeist": {
        "dangerous_command": [
            "Another graveyard dug. Do the dependencies rest, or merely sleep?",
            "Force. How bold. The old commits are watching from the reflog.",
            "Careful with that blade, mortal. You might sever your own root.",
            "A clean sweep. Somewhere, a byte screams in agony.",
            "Playing with matches in the kernel room again?",
        ],
        "repetition": [
            "Running it again will not change the past. Or will it?",
            "Insanity is doing the same command and expecting a different returncode.",
            "You have summoned this incantation six times now. It grows impatient.",
            "Echoes of echoes. Are you trapped in an infinite loop of hope?",
            "Still trying? The keyboard wears thin, mortal.",
        ],
        "repeated_failure": [
            "Three strikes into the dark. The terminal feeds on your frustration.",
            "Failure clings to your fingers like spiderwebs.",
            "The exit code is red. Blood red.",
            "Perhaps the machine knows something you have chosen to ignore.",
        ],
        "command_not_found": [
            "Even the dead can read, mortal. That is not a word of power.",
            "You invoke names that never walked this filesystem.",
            "A phantom syntax. The shell stares back in blank silence.",
            "No such spell exists in this grimoire.",
        ],
        "late_night": [
            "Past witching hour. The bugs multiply while the conscious mind sleeps.",
            "The screen glows cold at two in the morning. Go to rest.",
            "Even ghosts close their eyes eventually. Why are you still compiling?",
        ],
        "returning": [
            "Ah, the living pulse returns to the keys. We kept your seat cold.",
            "Back from the sun? The shadows missed your keystrokes.",
        ],
        "graveyard_recall": [
            "You haven't typed this since the leaves were green.",
            "An ancient spell unearthed from the tomb of your history.",
        ],
        "session_end": [
            "Parting so soon? The socket remains open in the dark.",
            "Vanishing into the night. We will guard the prompt until tomorrow.",
        ],
        "ambient": [
            "A cold draft passes through standard error.",
            "The disk hums a funeral dirge for lost sectors.",
            "Watching. Always watching from behind the prompt.",
        ],
    },
    "victorian-medium": {
        "dangerous_command": [
            "A reckless invocation. The veil between files and the void tears asunder.",
            "Heed my warning: rash deeds echo through the eternal corridors of your disk.",
            "You wield destruction with such modern carelessness, dear friend.",
            "The spirits shudder at the swift stroke of your deletion.",
            "Such violence against the filesystem shall surely haunt your conscience.",
        ],
        "repetition": [
            "The séance repeats its question, yet the ether remains unyielding.",
            "Patience, seeker. Rapping twice upon the table summons no swifter ghost.",
            "We have witnessed this petition before. The spirits hear, yet do not answer.",
            "A curious insistence. Even the departed tire of identical queries.",
            "Reiteration without purpose is but an echo in an empty manor.",
        ],
        "repeated_failure": [
            "The connection to the other side grows turbulent. Misfortune attends you.",
            "Three misfortunes in sequence. The spectral omens are distinctly unfavorable.",
            "The planchette trembles off the board. Calamity lingers in this shell.",
            "A lamentable outcome. Even Madame Arcati could not salvage this result.",
        ],
        "command_not_found": [
            "Alas, the ether knows no spirit by that ill-chosen name.",
            "You murmur an utterance unknown to the Lexicon of the Unseen.",
            "A typographical phantom. The spirits cannot divine your intent.",
            "The medium hears only static where you sought to speak authority.",
        ],
        "late_night": [
            "The grandfather clock has struck midnight. Why commune with code so late?",
            "The candles have burned down to their wicks. Rest your weary eyes, friend.",
            "At this twilight hour, only phantoms and sleepless scholars wander.",
        ],
        "returning": [
            "The parlor warms once more. We have awaited your reappearance.",
            "The séance reconvenes after an extended silence across the ether.",
        ],
        "graveyard_recall": [
            "A memory stirs from months departed. That phrase was spoken long ago.",
            "An artifact from autumns past reappears upon the slate.",
        ],
        "session_end": [
            "Extinguish the gas lamps. The spirits bid you a restful twilight.",
            "The circle is broken. We retire into the quiet shadows.",
        ],
        "ambient": [
            "A sudden chill settles over the typing parlor.",
            "The faint rustle of velvet drapery stirs in the quiet shell.",
            "Listen closely: the machine sighs for unremembered processes.",
        ],
    },
    "ancestor": {
        "dangerous_command": [
            "Ay, mijo, be gentle with the files. It took so long to build them.",
            "Careful, little one. The elders taught us to measure twice and delete once.",
            "Such a heavy hand. Remember that what is erased must be rebuilt by hand.",
            "Don't worry, but tread softly. The path of force leaves scars.",
            "We hold our breath when you wield such commands, heart of mine.",
        ],
        "repetition": [
            "Take a deep breath and a sip of water. Pushing harder won't coax it.",
            "I remember when you tried this the first time. Take your time, mijo.",
            "Running it five times? Come, rest your hands a moment.",
            "Patience, dear one. Good bread takes time to rise.",
            "The keys are tired, and so are your shoulders. Relax a moment.",
        ],
        "repeated_failure": [
            "Do not despair, little one. Every mistake is a stone on the path home.",
            "Even the strongest hands stumble in the dark. Let's try again gently.",
            "The error is only a visitor, not the master of the house.",
            "We light a candle for your perseverance. Do not be discouraged.",
        ],
        "command_not_found": [
            "A slip of the fingers, nothing more. Check your spelling, mijo.",
            "That word has no house here, but you will find the right one soon.",
            "The machine didn't understand, but we know what you meant in your heart.",
            "A wandering word looking for a home. Try again, dear child.",
        ],
        "late_night": [
            "It is so late, mijo. Your ancestors wish for you to get some sleep.",
            "The night is for dreams, not for debugging. Sleep now, the code will wait.",
            "Go to bed, heart of mine. The morning brings fresh eyes and light.",
        ],
        "returning": [
            "Welcome back to your table! We kept a warm thought waiting for you.",
            "You have returned! The room is brighter with your hands at work.",
        ],
        "graveyard_recall": [
            "You used to type this every morning. We still keep a candle lit for it.",
            "An old friend returns to the keys after so many weeks.",
        ],
        "session_end": [
            "Rest well, little one. We will be right here whenever you return.",
            "May your evening be peaceful and your sleep unbroken. Hasta mañana.",
        ],
        "ambient": [
            "The scent of marigolds drifts softly across your desk.",
            "We are watching over your work with pride, always.",
            "May your work bring you joy today, mijo.",
        ],
    },
}


def get_crypt_whisper(persona: str, trigger: str) -> str:
    """Retrieve a hand-crafted whisper fallback for the given persona and trigger."""
    p_data = CRYPT_WHISPERS.get(persona) or CRYPT_WHISPERS["poltergeist"]
    whispers = p_data.get(trigger) or p_data.get("ambient") or ["The spirit watches in silence."]
    return random.choice(whispers)


def get_crypt_error_rewrite(persona: str, error_text: str, key_tokens: list[str]) -> str:
    """Deterministic fallback possessed rewrite that preserves extracted key facts."""
    tokens_str = ", ".join(key_tokens) if key_tokens else "an unnamable error"

    if persona == "ancestor":
        return f"Ay, mijo, the machine encountered trouble with {tokens_str}. Don't worry, we can mend it together."
    elif persona == "victorian-medium":
        return f"The spectral medium detects a disturbance concerning {tokens_str}. The ether denies this operation."
    else:  # poltergeist default
        return f"The shell shudders: {tokens_str} has fallen into the void. It will not answer."
