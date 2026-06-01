package com.salmon.studion.domain.clip.entity;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.experimental.SuperBuilder;

@Getter
@SuperBuilder
@NoArgsConstructor
public class ClipDeleteEventDocument extends ClipEventDocument {
    private Boolean undoable;
    private Boolean undone;
}
