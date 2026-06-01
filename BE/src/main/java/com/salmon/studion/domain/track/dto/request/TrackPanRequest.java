package com.salmon.studion.domain.track.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackPanRequest extends TrackRequest {
    private Integer trackId;
    private Integer pan;

    @Override
    public void validate() {
        if (getProjectId() == null || trackId == null || pan == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
