package com.salmon.studion.domain.track.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackRenameRequest extends TrackRequest {
    private Integer trackId;
    private String name;

    @Override
    public void validate() {
        if (getProjectId() == null || trackId == null || name == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
