package com.salmon.studion.domain.project.dto.websocket;

import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;

public record ProjectKeyModifiedResponse(
        RootNote rootNote,
        ProjectMode mode
) {
}
