package com.salmon.studion.domain.audio.render;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.audio.render.dto.AudioVersionRenderSnapshot;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class AudioVersionRenderSnapshotSerializer {

    private final ObjectMapper objectMapper;

    public String serialize(AudioVersionRenderSnapshot snapshot) {
        try {
            return objectMapper.writeValueAsString(snapshot);
        } catch (JsonProcessingException exception) {
            throw new BusinessException(ErrorCode.FAIL, "오디오 버전 렌더 스냅샷 직렬화에 실패했습니다.");
        }
    }

    public AudioVersionRenderSnapshot deserialize(String snapshotJson) {
        try {
            return objectMapper.readValue(snapshotJson, AudioVersionRenderSnapshot.class);
        } catch (JsonProcessingException exception) {
            throw new BusinessException(ErrorCode.FAIL, "오디오 버전 렌더 스냅샷 역직렬화에 실패했습니다.");
        }
    }
}
