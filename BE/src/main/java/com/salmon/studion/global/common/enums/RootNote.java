package com.salmon.studion.global.common.enums;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum RootNote {
    C("C"),
    C_SHARP("C#"),
    D("D"),
    E_FLAT("Eb"),
    E("E"),
    F("F"),
    F_SHARP("F#"),
    G("G"),
    A_FLAT("Ab"),
    A("A"),
    B_FLAT("Bb"),
    B("B");

    private final String value;
}
