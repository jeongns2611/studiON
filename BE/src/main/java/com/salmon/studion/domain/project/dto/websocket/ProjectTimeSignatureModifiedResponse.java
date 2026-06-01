package com.salmon.studion.domain.project.dto.websocket;

public record ProjectTimeSignatureModifiedResponse(
        Integer timeSigNumerator,
        Integer timeSigDenominator
) {
}
