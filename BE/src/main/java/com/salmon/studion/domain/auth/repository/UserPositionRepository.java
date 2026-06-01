package com.salmon.studion.domain.auth.repository;

import com.salmon.studion.domain.auth.entity.UserPosition;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserPositionRepository extends JpaRepository<UserPosition, UserPosition.UserPositionId> {

}
