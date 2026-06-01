package com.salmon.studion.domain.eq.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackEqLockRequest extends TrackEqRequest {

    private Integer trackEqId;
    private Boolean isLocked;

    @Override
    public void validate() {
        if (getProjectId() == null || trackEqId == null || isLocked == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
