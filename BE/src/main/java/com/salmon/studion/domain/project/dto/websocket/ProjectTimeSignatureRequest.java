package com.salmon.studion.domain.project.dto.websocket;

public record ProjectTimeSignatureRequest(
        Integer timeSigNumerator,
        Integer timeSigDenominator
) {
}
