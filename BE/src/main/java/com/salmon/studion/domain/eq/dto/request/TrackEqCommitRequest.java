package com.salmon.studion.domain.eq.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackEqCommitRequest extends TrackEqRequest {

    private Integer trackEqId;

    @Override
    public void validate() {
        if (getProjectId() == null || trackEqId == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
