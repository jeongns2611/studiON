package com.salmon.studion.domain.auth.repository;

import com.salmon.studion.domain.auth.entity.PositionDetail;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface PositionDetailRepository extends JpaRepository<PositionDetail, Integer> {

    // 모든 포지션 조회
    List<PositionDetail> findAllByOrderByPositionGroup_OrderAscOrderAsc();
}
