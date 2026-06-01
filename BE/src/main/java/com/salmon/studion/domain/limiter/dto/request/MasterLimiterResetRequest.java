package com.salmon.studion.domain.limiter.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.NoArgsConstructor;

@NoArgsConstructor
public class MasterLimiterResetRequest extends MasterLimiterRequest {

    @Override
    public void validate() {
        if (getProjectId() == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
