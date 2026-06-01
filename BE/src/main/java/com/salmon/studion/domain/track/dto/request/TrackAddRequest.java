package com.salmon.studion.domain.track.dto.request;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class TrackAddRequest extends TrackRequest{
    private String name;
    private String type;

    @Override
    public void validate() {
        if(getProjectId() == null || name == null || type == null)
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
    }
}
