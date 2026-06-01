package com.salmon.studion.domain.audio.dto.request;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AudioVersionCreateRequest {

    public static final int MAX_AUDIO_VERSION_NAME = 50;
    public static final int MAX_AUDIO_VERSION_MEMO = 255;

    @NotEmpty(message = "프로젝트 버전 이름은 필수 입니다.")
    @Size(max = MAX_AUDIO_VERSION_NAME, message = "프로젝트 버전 이름은 50자를 넘을 수 없습니다.")
    private String name;

    @Size(max = MAX_AUDIO_VERSION_MEMO, message = "프로젝트 버전에 대한 설명은 255자를 넘을 수 없습니다.")
    private String memo;
}
