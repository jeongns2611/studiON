package com.salmon.studion.domain.auth.dto.response;

public record PositionDetailResponse(
        Integer code,
        String name,
        Integer order,
        Integer groupCode,
        String groupName,
        Integer groupOrder
) {
}
