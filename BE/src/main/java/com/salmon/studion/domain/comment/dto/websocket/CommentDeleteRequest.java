package com.salmon.studion.domain.comment.dto.websocket;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class CommentDeleteRequest extends CommentRequest {

    private Integer commentId;

    @Override
    public void validate() {
        if (getProjectId() == null || commentId == null) {
            throw new BusinessException(ErrorCode.INVALID_REQUEST);
        }
    }
}
