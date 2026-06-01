package com.salmon.studion.domain.audio.dto.request;

import jakarta.validation.constraints.NotEmpty;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class AudioListRequest {

    @NotEmpty(message = "클립 ID 목록은 필수입니다.")
    private List<Integer> clipIds;
}
